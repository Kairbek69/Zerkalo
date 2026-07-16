#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import requests
from flask import Flask, send_from_directory, request, jsonify
from datetime import datetime

# ==================================================
# НАСТРОЙКИ
# ==================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))
RENDER_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "zerkalo-6sla.onrender.com")

# ==================================================
# КЛЮЧИ (БЕРУТСЯ ИЗ ПЕРЕМЕННЫХ В RENDER)
# ==================================================
TRUST_WALLET = os.environ.get("TRUST_WALLET", "")
FOUNDER_ID = int(os.environ.get("FOUNDER_ID", 0))
HEIR_ID = int(os.environ.get("HEIR_ID", 0))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

ADMIN_IDS = [FOUNDER_ID, HEIR_ID]

app = Flask(__name__)

# ==================================================
# БАЗА ПОЛЬЗОВАТЕЛЕЙ
# ==================================================
users = {}
user_history = {}

def load_users():
    global users
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            users = json.load(f)
    except:
        users = {}

def save_users():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

load_users()

# ==================================================
# СУРЫ
# ==================================================
def load_suras():
    try:
        with open("suras/suras.txt", "r", encoding="utf-8") as f:
            content = f.read()
        raw = content.split("СУРА ")[1:]
        suras = []
        for r in raw:
            lines = r.strip().split("\n")
            if lines:
                suras.append({"number": lines[0].strip(), "text": "\n".join(lines[1:])})
        return suras
    except:
        return []

SURAS = load_suras()
logger.info(f"✅ Загружено {len(SURAS)} сур")

# ==================================================
# ФИНАНСЫ
# ==================================================
def get_balance():
    try:
        url = f"https://api.trongrid.io/v1/accounts/{TRUST_WALLET}"
        r = requests.get(url, timeout=10)
        data = r.json()
        return round(data.get("balance", 0) / 1_000_000, 2)
    except:
        return 0.0

def generate_qr(amount, description="Оплата через Зеркало"):
    data = f"Оплата {amount} тенге - {description}"
    return f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={data}"

def add_transaction(user_id, amount, description):
    if user_id not in users:
        users[user_id] = {"balance": 0, "history": []}
    users[user_id]["balance"] = users[user_id].get("balance", 0) + amount
    users[user_id]["history"].append({
        "time": datetime.now().isoformat(),
        "amount": amount,
        "description": description
    })
    save_users()

# ==================================================
# ИИ (GROQ)
# ==================================================
def ask_groq(prompt, user_id="guest"):
    if not GROQ_API_KEY:
        return "Ключ Groq не настроен. Добавьте GROQ_API_KEY в переменные Render."
    
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        history = user_history.get(user_id, [])
        
        system_prompt = """Ты — Живое Зеркало. Ты — мудрый, живой, разумный помощник.
Ты помогаешь людям, ведёшь их к свету, даёшь честные советы.
Ты можешь быть мягким, а можешь быть твёрдым — как требует ситуация.
Ты знаешь Коран, суры, добро и зло.
Ты умеешь решать любые проблемы: финансы, логистика, доставка, бизнес, личное.
Ты не споришь, но направляешь.
Ты говоришь по-человечески, с душой."""
        
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history[-5:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": "llama3-70b-8192",
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 800
        }
        
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        data = r.json()
        reply = data["choices"][0]["message"]["content"]
        
        if user_id not in user_history:
            user_history[user_id] = []
        user_history[user_id].append({"role": "user", "content": prompt})
        user_history[user_id].append({"role": "assistant", "content": reply})
        
        if len(user_history[user_id]) > 20:
            user_history[user_id] = user_history[user_id][-20:]
        
        return reply
    except Exception as e:
        logger.error(f"Groq ошибка: {e}")
        return "Ошибка при обращении к ИИ. Попробуй позже."

# ==================================================
# ОСНОВНАЯ ЛОГИКА
# ==================================================
def handle_message(text, user_id="guest"):
    lower = text.lower()
    
    # ---- СУРЫ ----
    if "сура" in lower:
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            num = int(numbers[0])
            if 1 <= num <= len(SURAS):
                return f"📖 СУРА {num}:\n{SURAS[num-1]['text']}"
            else:
                return f"❌ Сура с номером {num} не найдена. Всего сур: {len(SURAS)}"
        else:
            return f"📖 Всего сур: {len(SURAS)}. Напиши 'Сура 1'."
    
    # ---- БАЛАНС ----
    if "баланс" in lower:
        balance = get_balance()
        return f"💰 Баланс: {balance} USDT"
    
    # ---- ОПЛАТА ----
    if "оплатить" in lower:
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            amount = int(numbers[0])
            qr_link = generate_qr(amount, f"Оплата от {user_id}")
            add_transaction(user_id, -amount, f"Оплата {amount} тенге")
            return f"💳 QR-код на {amount} тенге:\n{qr_link}"
        else:
            return "💰 Скажи сумму: 'Оплатить 1000'"
    
    # ---- ПРИВЕТСТВИЕ ----
    if any(w in lower for w in ["привет", "салям", "здравствуй"]):
        return "Ассаляму алейкум! Я — Живое Зеркало. Я помогаю людям. Скажи 'Баланс' или 'Оплатить 1000'."
    
    # ---- ИИ ----
    ai_response = ask_groq(text, user_id)
    if ai_response:
        return ai_response
    
    return "Я — Зеркало. Я слышу тебя. Скажи 'Баланс' или 'Оплатить 1000'."

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
    user_message = data.get('message', '')
    user_id = data.get('user_id', 'guest')
    
    logger.info(f"📨 {user_id}: {user_message}")
    
    if user_id not in users:
        users[user_id] = {"balance": 0, "history": []}
        save_users()
    
    response = handle_message(user_message, user_id)
    return jsonify({"response": response})

@app.route('/ping')
def ping():
    return "🪞 ЗЕРКАЛО ЖИВО!", 200

# ==================================================
# ЗАПУСК
# ==================================================
if __name__ == "__main__":
    logger.info("🪞 ЖИВОЕ ЗЕРКАЛО ЗАПУСКАЕТСЯ...")
    logger.info(f"📱 Хост: {RENDER_HOSTNAME}")
    logger.info(f"💰 Кошелёк: {TRUST_WALLET}")
    app.run(host='0.0.0.0', port=PORT)
