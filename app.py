import os
import json
import base64
import asyncio
import threading
import subprocess
from flask import Flask, request, jsonify
from flask_cors import CORS

# Импорт модулей
import redis
import sqlite3
from groq import Groq
import google.generativeai as genai
import edge_tts
import requests

app = Flask(__name__)
CORS(app)

# --- Конфигурация ---
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

# Подключение к Redis
r = redis.Redis.from_url(REDIS_URL)

# Подключение к SQLite
conn = sqlite3.connect('zerkalo.db', check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, action TEXT, details TEXT, timestamp TEXT)")

# Подключение к Gemini
genai.configure(api_key=GEMINI_API_KEY)
vision_model = genai.GenerativeModel('gemini-1.5-pro')

# Подключение к Groq
groq_client = Groq(api_key=GROQ_API_KEY)

# --- Функции ---
def log_action(user_id, action, details=""):
    import datetime
    c.execute("INSERT INTO logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, action, details, datetime.datetime.now().isoformat()))
    conn.commit()

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        if data.get("type") != "frame":
            return jsonify({"error": "Invalid type"}), 400

        image_data = data["data"].split(",")[1]
        image_bytes = base64.b64decode(image_data)

        # Анализ через Gemini Vision
        response = vision_model.generate_content([
            "Ты — Зеркало. Ты видишь экран человека. Определи, какое приложение открыто, какой элемент активен (кнопка, поле ввода), и дай короткую голосовую подсказку. Не используй сложные термины. Ответь строго JSON: {'app': '...', 'element': '...', 'hint': '...'}",
            {"mime_type": "image/jpeg", "data": image_bytes}
        ])

        result_text = response.text.strip()
        result_text = result_text.replace("```json", "").replace("```", "").strip()

        try:
            result = json.loads(result_text)
        except:
            result = {"app": "Неизвестно", "element": "Неизвестно", "hint": "Повторите действие"}

        # Генерация голоса через Edge-TTS
        tts = edge_tts.Communicate(result.get("hint", "Подсказка"), voice="ru-RU-SvetlanaNeural")
        audio_file = "audio_output.mp3"
        asyncio.run(tts.save(audio_file))

        return jsonify({
            "type": "instruction",
            "data": result,
            "audio_url": "https://zerkalo.onrender.com/audio_output.mp3"
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/status', methods=['GET'])
def status():
    return jsonify({"status": "running", "version": "2.0", "mode": "Комфорт по жизни!"})

@app.route('/deploy', methods=['POST'])
def auto_deploy():
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Авто-обновление от Зеркала"], check=True)
        subprocess.run(["git", "push"], check=True)
        return jsonify({"status": "deployed"})
    except:
        return jsonify({"status": "error"}), 500

# --- Запуск ---
if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
