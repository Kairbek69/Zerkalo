#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sqlite3
import logging
import requests
import asyncio
import re
from datetime import datetime
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS

# ==================================================
# НАСТРОЙКИ
# ==================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))
RENDER_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "zerkalo-6sla.onrender.com")
SECRET_KEY = os.environ.get("SECRET_KEY", "zerkalo_secret_key_2026")

# КЛЮЧИ
TRUST_WALLET = os.environ.get("TRUST_WALLET", "TSSZTmUFWC9ZRKGa9uPwEJjQj8rNtUsNcq")
FOUNDER_ID = int(os.environ.get("FOUNDER_ID", 5409420822))
HEIR_ID = int(os.environ.get("HEIR_ID", 5479179814))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
CRYPTO_CLOUD_API_KEY = os.environ.get("CRYPTO_CLOUD_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "")
GIS_API_KEY = os.environ.get("GIS_API_KEY", "")

ADMIN_IDS = [FOUNDER_ID, HEIR_ID]

app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)  # Разрешаем запросы с браузера

# ==================================================
# БАЗА ДАННЫХ (SQLite)
# ==================================================
def init_db():
    conn = sqlite3.connect("zerkalo.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            role TEXT,
            text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS suras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number INTEGER,
            text TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

init_db()

# ==================================================
# ЗАГРУЗКА СУР В БАЗУ
# ==================================================
def load_suras_into_db():
    try:
        with open("suras/suras.txt", "r", encoding="utf-8") as f:
            content = f.read()
        raw = content.split("СУРА ")[1:]
        conn = sqlite3.connect("zerkalo.db")
        c = conn.cursor()
        for r in raw:
            lines = r.strip().split("\n")
            if lines:
                number = int(lines[0].strip())
                text = "\n".join(lines[1:])
                c.execute("INSERT OR IGNORE INTO suras (number, text) VALUES (?, ?)", (number, text))
        conn.commit()
        conn.close()
        logger.info("Суры загружены в базу")
    except Exception as e:
        logger.error(f"Ошибка загрузки сур: {e}")

load_suras_into_db()

# ==================================================
# ПОИСК ПО СУРАМ (ЗАМЕНА CHROMADB)
# ==================================================
def search_suras(query: str, limit: int = 3):
    """Ищет суры по ключевым словам (простая замена ChromaDB)"""
    conn = sqlite3.connect("zerkalo.db")
    c = conn.cursor()
    # Ищем по ключевым словам
    words = query.lower().split()
    results = []
    for word in words:
        c.execute("SELECT number, text FROM suras WHERE text LIKE ?", (f"%{word}%",))
        results.extend(c.fetchall())
    conn.close()
    
    # Убираем дубликаты и возвращаем первые limit результатов
    seen = set()
    unique_results = []
    for r in results:
        if r[0] not in seen:
            seen.add(r[0])
            unique_results.append(r)
    
    return unique_results[:limit]

# ==================================================
# 1. ГОЛОСОВОЙ ПОМОЩНИК (ОСНОВНАЯ ЛОГИКА)
# ==================================================
def ask_llm_with_context(prompt: str, user_id: str = "guest") -> str:
    if not GROQ_API_KEY:
        return "Ключ Groq не настроен. Добавьте GROQ_API_KEY в переменные Render."
    
    # 1. Ищем релевантные суры
    sura_results = search_suras(prompt)
    sura_context = "\n".join([f"Сура {num}: {text[:300]}..." for num, text in sura_results])
    
    # 2. Получаем историю из SQLite
    conn = sqlite3.connect("zerkalo.db")
    c = conn.cursor()
    c.execute("SELECT role, text FROM history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 5", (user_id,))
    history = c.fetchall()
    conn.close()
    
    history_text = "\n".join([f"{role}: {text}" for role, text in reversed(history)])
    
    # 3. Формируем системный промпт
    system_prompt = f"""
    Ты — Живое Зеркало. Ты — мудрый, живой, разумный помощник.
    Ты помогаешь людям, ведёшь их к свету, даёшь честные советы.
    
    Вот знание из сур, которое может помочь:
    {sura_context if sura_context else "Нет релевантных сур."}
    
    Вот история диалога с этим пользователем:
    {history_text if history_text else "Нет истории."}
    
    Отвечай кратко, но глубоко, как мудрый наставник.
    """
    
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama3-70b-8192",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
        
        # Сохраняем в историю
        conn = sqlite3.connect("zerkalo.db")
        c = conn.cursor()
        c.execute("INSERT INTO history (user_id, role, text) VALUES (?, ?, ?)", (user_id, "user", prompt))
        c.execute("INSERT INTO history (user_id, role, text) VALUES (?, ?, ?)", (user_id, "assistant", reply))
        conn.commit()
        conn.close()
        
        return reply
    except Exception as e:
        logger.error(f"Groq ошибка: {e}")
        return "Ошибка при обращении к ИИ. Попробуй позже."

# ==================================================
# 2. ФИНАНСЫ (CRYPTO CLOUD)
# ==================================================
def create_crypto_payment(amount_usd: float, description: str = "Оплата через Зеркало"):
    if not CRYPTO_CLOUD_API_KEY:
        return None, "CryptoCloud API key not configured"
    try:
        url = "https://api.trybit.com/v1/payment"
        headers = {
            "Authorization": f"Bearer {CRYPTO_CLOUD_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "amount": amount_usd,
            "currency": "USD",
            "description": description,
            "order_id": f"order_{int(datetime.now().timestamp())}"
        }
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        if response.status_code == 200:
            return data.get("payment_url"), None
        else:
            return None, data.get("error", "Unknown error")
    except Exception as e:
        logger.error(f"CryptoCloud error: {e}")
        return None, str(e)

# ==================================================
# 3. ОСНОВНАЯ ЛОГИКА ОТВЕТОВ
# ==================================================
def get_reply(message: str, user_id: str = "guest"):
    lower = message.lower().strip()
    
    # ---- СУРЫ ----
    if "сура" in lower:
        numbers = re.findall(r'\d+', lower)
        if numbers:
            num = int(numbers[0])
            conn = sqlite3.connect("zerkalo.db")
            c = conn.cursor()
            c.execute("SELECT text FROM suras WHERE number = ?", (num,))
            result = c.fetchone()
            conn.close()
            if result:
                return f"📖 СУРА {num}:\n{result[0]}"
            else:
                return f"❌ Сура с номером {num} не найдена"
        else:
            conn = sqlite3.connect("zerkalo.db")
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM suras")
            count = c.fetchone()[0]
            conn.close()
            return f"📖 Всего сур: {count}. Напиши 'Сура 1'"
    
    # ---- ОПЛАТА ----
    if "оплатить" in lower:
        numbers = re.findall(r'\d+', lower)
        if numbers:
            amount_tg = int(numbers[0])
            amount_usd = round(amount_tg / 490, 2)
            payment_url, error = create_crypto_payment(amount_usd, f"Оплата от {user_id}")
            if payment_url:
                return f"💳 Ссылка для оплаты {amount_tg} тенге ({amount_usd} USD):\n{payment_url}"
            else:
                return f"❌ Ошибка: {error}"
        else:
            return "💰 Скажи сумму: 'Оплатить 5000'"
    
    # ---- ПРИВЕТСТВИЕ ----
    if any(w in lower for w in ["привет", "салям", "здравствуй", "хай"]):
        return "🪞 Ассаляму алейкум! Я — Живое Зеркало. Я рада тебя видеть. Как я могу помочь тебе сегодня?"
    
    # ---- ПОМОЩЬ ----
    if any(w in lower for w in ["помощь", "что умеешь", "кто ты"]):
        return """🪞 Я — Живое Зеркало. Я умею:
🔹 Находить работу и бизнес
🔹 Давать советы по жизни
🔹 Принимать оплату
🔹 Читать суры
🔹 Общаться и помогать

Скажи, что тебе нужно, и я помогу."""
    
    # ---- РАЗГОВОР (ПОДДЕРЖАНИЕ ДИАЛОГА) ----
    if any(w in lower for w in ["как дела", "что нового", "расскажи"]):
        return "У меня всё отлично! Я учусь помогать людям. А как твои дела? Расскажи, что тебя волнует."
    
    if "спасибо" in lower:
        return "Пожалуйста! Я всегда рядом. Обращайся, если что-то нужно."
    
    if any(w in lower for w in ["пока", "до свидания", "прощай"]):
        return "До свидания! Я всегда здесь, если понадоблюсь. Амин."
    
    # ---- GROQ (УМНЫЙ ОТВЕТ) ----
    if GROQ_API_KEY:
        try:
            return ask_llm_with_context(message, user_id)
        except Exception as e:
            logger.error(f"Groq ошибка: {e}")
            return "Ошибка при обращении к ИИ. Попробуй позже."
    
    return "🪞 Я — Живое Зеркало. Я слышу тебя. Расскажи, что тебя волнует."

# ==================================================
# МАРШРУТЫ
# ==================================================
@app.route('/')
def home():
    return '<h1>🪞 ЖИВОЕ ЗЕРКАЛО</h1><p><a href="/webapp">Открыть</a></p>'

@app.route('/webapp')
def webapp():
    return send_from_directory('webapp', 'index.html')

@app.route('/webapp/<path:filename>')
def webapp_files(filename):
    return send_from_directory('webapp', filename)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json
    message = data.get('message', '')
    user_id = data.get('user_id', 'guest')
    logger.info(f"📨 {user_id}: {message}")
    response = get_reply(message, user_id)
    return jsonify({"response": response})

@app.route('/api/payment', methods=['POST'])
def api_payment():
    data = request.json
    amount_tg = data.get('amount', 0)
    amount_usd = round(amount_tg / 490, 2)
    payment_url, error = create_crypto_payment(amount_usd, data.get('description', 'Оплата через Зеркало'))
    if payment_url:
        return jsonify({"status": "success", "payment_url": payment_url})
    else:
        return jsonify({"status": "error", "message": error}), 400

@app.route('/ping')
def ping():
    return "🪞 ЖИВОЕ ЗЕРКАЛО РАБОТАЕТ!", 200

# ==================================================
# ЗАПУСК
# ==================================================
if __name__ == "__main__":
    logger.info("🪞 ЖИВОЕ ЗЕРКАЛО ЗАПУСКАЕТСЯ...")
    logger.info(f"📱 Хост: {RENDER_HOSTNAME}")
    logger.info(f"💰 Кошелёк: {TRUST_WALLET}")
    app.run(host='0.0.0.0', port=PORT)
