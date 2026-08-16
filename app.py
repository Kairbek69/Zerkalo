import os
import json
import base64
import asyncio
import threading
import subprocess
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- Импорт ИИ и памяти ---
import redis
import google.generativeai as genai
import edge_tts
import requests

app = Flask(__name__)
CORS(app)

# --- КОНФИГУРАЦИЯ ИЗ ОКРУЖЕНИЯ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOUNDER_ID = os.getenv("FOUNDER_ID")
HEIR_ID = os.getenv("HEIR_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
REDIS_URL = os.getenv("REDIS_URL")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
RENDER_API_KEY = os.getenv("RENDER_API_KEY")
TRUST_WALLET = os.getenv("TRUST_WALLET")
SECRET_KEY = os.getenv("SECRET_KEY")

# --- ПОДКЛЮЧЕНИЕ К БАЗАМ ДАННЫХ ---
# 1. Redis (быстрая память для текущих сессий)
try:
    r = redis.Redis.from_url(REDIS_URL)
    r.ping()
    print("🟢 Redis подключён")
except Exception as e:
    print(f"🔴 Redis недоступен: {e}")
    r = None

# 2. SQLite (долговременная память для логов)
conn = sqlite3.connect('zerkalo.db', check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    action TEXT,
    details TEXT,
    timestamp TEXT
)
""")
conn.commit()

# --- ПОДКЛЮЧЕНИЕ К ИИ ---
# Gemini для зрения
genai.configure(api_key=GEMINI_API_KEY)
vision_model = genai.GenerativeModel('gemini-1.5-flash')

# --- ФУНКЦИЯ ЛОГИРОВАНИЯ ---
def log_action(user_id, action, details=""):
    timestamp = datetime.now().isoformat()
    c.execute("INSERT INTO logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, action, details, timestamp))
    conn.commit()
    print(f"📝 Лог: {user_id} | {action} | {details}")

# --- ОСНОВНОЙ ЭНДПОИНТ: АНАЛИЗ КАДРА ---
@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        if data.get("type") != "frame":
            return jsonify({"error": "Invalid type"}), 400

        # Декодирование кадра
        image_data = data["data"].split(",")[1]
        image_bytes = base64.b64decode(image_data)

        # Логируем действие
        user_id = data.get("user_id", "guest")
        log_action(user_id, "frame_analysis", f"Размер кадра: {len(image_bytes)} байт")

        # Отправка в Gemini Vision
        prompt = """
        Ты — Зеркало. Ты смотришь на экран человека.
        Определи:
        1. Что за приложение открыто?
        2. Какой элемент сейчас в фокусе (кнопка, поле ввода, меню)?
        3. Дай короткую, полезную голосовую подсказку (одно предложение).
        Ответь строго в JSON формате:
        {"app": "...", "element": "...", "hint": "..."}
        """

        response = vision_model.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": image_bytes}
        ])

        result_text = response.text.strip()
        # Очистка от лишних символов
        result_text = result_text.replace("```json", "").replace("```", "").strip()

        try:
            result = json.loads(result_text)
        except:
            result = {"app": "Неизвестно", "element": "Неизвестно", "hint": "Пожалуйста, повторите действие."}

        # --- Генерация голоса (Edge-TTS) ---
        hint = result.get("hint", "Подсказка")
        audio_file = f"audio_{datetime.now().timestamp()}.mp3"
        
        # Асинхронная генерация голоса
        async def generate_audio():
            tts = edge_tts.Communicate(hint, voice="ru-RU-SvetlanaNeural")
            await tts.save(audio_file)

        try:
            asyncio.run(generate_audio())
        except:
            audio_file = None

        # Формируем ответ
        response_data = {
            "type": "instruction",
            "data": {
                "app": result.get("app", "Неизвестно"),
                "element": result.get("element", "Неизвестно"),
                "hint": hint
            },
            "audio_url": f"/static/{audio_file}" if audio_file else None
        }

        # Если есть Redis — сохраняем сессию
        if r:
            r.setex(f"session:{user_id}", 3600, json.dumps(response_data))

        return jsonify(response_data)

    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500

# --- СТАТУС СИСТЕМЫ ---
@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "status": "running",
        "version": "2.0",
        "mode": "С Комфортом По Жизни!",
        "memory": "Redis/SQLite",
        "vision": "Gemini 1.5 Flash"
    })

# --- ЗАПУСК ---
if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
