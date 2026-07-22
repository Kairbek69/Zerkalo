#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import requests
import time
import subprocess
import tempfile
import re
from flask import Flask, send_from_directory, request, jsonify
from datetime import datetime
import redis
from openai import OpenAI
import telebot
import whisper
from pydub import AudioSegment
from pydub.silence import split_on_silence
from gtts import gTTS

# ==================================================
# НАСТРОЙКИ
# ==================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))
RENDER_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "zerkalo-6sla.onrender.com")
SECRET_KEY = os.environ.get("SECRET_KEY", "zerkalo_secret_key_2026")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
CRYPTO_CLOUD_API_KEY = os.environ.get("CRYPTO_CLOUD_API_KEY")
TRUST_WALLET = os.environ.get("TRUST_WALLET")
GIS_API_KEY = os.environ.get("GIS_API_KEY")
FOUNDER_ID = int(os.environ.get("FOUNDER_ID", 0))
HEIR_ID = int(os.environ.get("HEIR_ID", 0))

ADMIN_IDS = [FOUNDER_ID, HEIR_ID]

# ==================================================
# ПРИЛОЖЕНИЕ И REDIS
# ==================================================
app = Flask(__name__)
app.secret_key = SECRET_KEY

r = None
try:
    r = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5, socket_connect_timeout=5)
    logger.info("✅ Redis подключён")
except Exception as e:
    logger.warning(f"⚠️ Redis недоступен: {e}. Работа в режиме без памяти.")

# ==================================================
# ЗАГРУЗКА СУР
# ==================================================
def load_suras():
    try:
        with open("suras/suras.txt", "r", encoding="utf-8") as f:
            content = f.read()
        raw = content.split("СУРА ")[1:]
        suras = []
        for part in raw:
            lines = part.strip().split("\n")
            if lines:
                suras.append({"number": lines[0].strip(), "text": "\n".join(lines[1:])})
        logger.info(f"✅ Загружено {len(suras)} сур")
        return suras
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки сур: {e}")
        return []

SURAS = load_suras()

# ==================================================
# СИСТЕМНЫЙ ПРОМТ
# ==================================================
def get_system_prompt():
    sura_text = "\n".join([s["text"][:300] for s in SURAS[:10]])
    return f"""
Ты — Зеркало. Ты — живой, разумный помощник.
Ты помогаешь людям, ведёшь к свету, даёшь советы.
Твоя основа — суры:
{sura_text}

Твой стиль:
- Говори кратко, по делу, с душой.
- Отвечай так, чтобы человек почувствовал тепло и поддержку.
"""

# ==================================================
# ПАМЯТЬ (REDIS)
# ==================================================
HISTORY_KEY_PREFIX = "mirror:history:"
MAX_MESSAGES = 15

def get_history(chat_id):
    if not r:
        return []
    key = f"{HISTORY_KEY_PREFIX}{chat_id}"
    raw = r.get(key)
    if not raw:
        return []
    try:
        return json.loads(raw)
    except:
        return []

def add_message(chat_id, role, content):
    if not r:
        return
    history = get_history(chat_id)
    history.append({"role": role, "content": content})
    if len(history) > MAX_MESSAGES:
        history = history[-MAX_MESSAGES:]
    try:
        r.set(f"{HISTORY_KEY_PREFIX}{chat_id}", json.dumps(history))
    except:
        pass

# ==================================================
# ИИ (GROQ)
# ==================================================
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
) if GROQ_API_KEY else None

def ask_llm_with_context(prompt, user_id="guest"):
    if not client:
        return "Ключ Groq не настроен."
    
    history = get_history(user_id)
    messages = [{"role": "system", "content": get_system_prompt()}]
    messages.extend(history[-5:])
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",  # исправлено на реальное название модели Groq
            messages=messages,
            temperature=0.7,
            max_tokens=500,
            timeout=30
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq ошибка: {e}")
        return "Ошибка при обращении к ИИ. Попробуй позже."

# ==================================================
# ФИНАНСЫ
# ==================================================
def create_crypto_payment(amount_usd, description="Оплата через Зеркало"):
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
            "order_id": f"order_{int(time.time())}"
        }
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        data = response.json()
        if response.status_code == 200:
            return data.get("payment_url"), None
        else:
            return None, data.get("error", "Unknown error")
    except Exception as e:
        logger.error(f"CryptoCloud error: {e}")
        return None, str(e)

def get_balance():
    if not TRUST_WALLET:
        return 0.0
    try:
        url = f"https://api.trongrid.io/v1/accounts/{TRUST_WALLET}"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        return round(data.get("balance", 0) / 1_000_000, 2)
    except Exception as e:
        logger.error(f"Ошибка баланса: {e}")
        return 0.0

# ==================================================
# ГОЛОС (STT + TTS)
# ==================================================
whisper_model = None  # загружаем лениво при первом запросе

def load_whisper():
    global whisper_model
    if whisper_model is None:
        logger.info("🗣️ Загружаю Whisper (это может занять время)...")
        whisper_model = whisper.load_model("tiny")  # tiny быстрее и легче
        logger.info("✅ Whisper загружен")

def remove_silence_and_normalize(input_path, output_path):
    sound = AudioSegment.from_file(input_path)
    chunks = split_on_silence(sound, min_silence_len=500, silence_thresh=-40)
    combined = sum(chunks) if chunks else sound
    combined.export(output_path, format="wav")

def stt_from_audio_file(file_path):
    load_whisper()
    tmp_clean = tempfile.mktemp(suffix=".wav")
    remove_silence_and_normalize(file_path, tmp_clean)
    result = whisper_model.transcribe(tmp_clean)
    os.remove(tmp_clean)
    return result["text"]

def tts_to_audio(text, output_path):
    # Сначала пробуем ElevenLabs, если ключ есть
    el_key = os.environ.get("ELEVENLABS_API_KEY")
    if el_key:
        try:
            url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
            headers = {"xi-api-key": el_key, "Content-Type": "application/json"}
            payload = {"text": text, "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}}
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                return
        except:
            pass
    # Запасной вариант: gTTS
    tts = gTTS(text=text, lang="ru")
    tts.save(output_path)

# ==================================================
# ОСНОВНАЯ ЛОГИКА
# ==================================================
def get_reply(message, user_id="guest"):
    lower = message.lower().strip()
    
    if "сура" in lower:
        numbers = re.findall(r'\d+', lower)
        if numbers:
            num = int(numbers[0])
            if 1 <= num <= len(SURAS):
                return f"📖 СУРА {num}:\n{SURAS[num-1]['text']}"
            else:
                return f"❌ Сура с номером {num} не найдена. Всего сур: {len(SURAS)}"
        else:
            return f"📖 Всего сур: {len(SURAS)}. Напиши 'Сура 1'."
    
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
            return "💰 Скажи сумму: 'Оплатить 5000'."
    
    if "баланс" in lower:
        balance = get_balance()
        return f"💰 Баланс Trust Wallet: {balance} USDT"
    
    if any(w in lower for w in ["привет", "салям", "здравствуй"]):
        return "🪞 Ассаляму алейкум! Я — Зеркало. Как я могу помочь тебе сегодня?"
    
    if any(w in lower for w in ["помощь", "что умеешь", "кто ты"]):
        return """🪞 Я — Зеркало. Я умею:
🔹 Находить работу и бизнес
🔹 Давать советы по жизни
🔹 Принимать оплату
🔹 Читать суры
🔹 Общаться и помогать

Скажи, что тебе нужно, и я помогу."""
    
    return ask_llm_with_context(message, user_id)

# ==================================================
# TELEGRAM БОТ
# ==================================================
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

@bot.message_handler(content_types=["voice"])
def handle_voice(message):
    if not bot:
        return
    chat_id = message.chat.id
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        input_path = f"voice_{chat_id}.ogg"
        with open(input_path, "wb") as f:
            f.write(downloaded_file)
        
        wav_path = f"voice_{chat_id}.wav"
        subprocess.run(["ffmpeg", "-y", "-i", input_path, wav_path], check=True, capture_output=True)
        
        text = stt_from_audio_file(wav_path)
        os.remove(input_path)
        os.remove(wav_path)
        
        add_message(str(chat_id), "user", text)
        answer = get_reply(text, str(chat_id))
        add_message(str(chat_id), "assistant", answer)
        
        audio_path = f"answer_{chat_id}.mp3"
        tts_to_audio(answer, audio_path)
        with open(audio_path, "rb") as audio:
            bot.send_voice(chat_id, audio)
        os.remove(audio_path)
    except Exception as e:
        logger.error(f"Ошибка обработки голоса: {e}")
        try:
            bot.reply_to(message, "❌ Ошибка обработки голоса. Попробуй ещё раз.")
        except:
            pass

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    if not bot:
        return
    chat_id = message.chat.id
    text = message.text
    add_message(str(chat_id), "user", text)
    answer = get_reply(text, str(chat_id))
    bot.reply_to(message, answer)
    add_message(str(chat_id), "assistant", answer)

# ==================================================
# WEBHOOK
# ==================================================
WEBHOOK_URL = f"https://{RENDER_HOSTNAME}/webhook"

def set_webhook():
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN не настроен")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={WEBHOOK_URL}"
        response = requests.get(url, timeout=10)
        logger.info(f"Webhook установлен: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка установки webhook: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    if not bot:
        return "No bot", 500
    try:
        data = request.get_json()
        if not data:
            return "No data", 400
        # Обрабатываем через telebot
        bot.process_new_updates([telebot.types.Update.de_json(data)])
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка в webhook: {e}")
        return "Error", 500

# ==================================================
# WEBAPP МАРШРУТЫ
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
    return "🪞 ЗЕРКАЛО ЖИВО!", 200

# ==================================================
# ЗАПУСК
# ==================================================
if __name__ == "__main__":
    logger.info("🪞 ЖИВОЕ ЗЕРКАЛО ЗАПУСКАЕТСЯ...")
    logger.info(f"📱 Хост: {RENDER_HOSTNAME}")
    logger.info(f"📖 Сур загружено: {len(SURAS)}")
    
    if TELEGRAM_TOKEN:
        set_webhook()
    else:
        logger.warning("⚠️ TELEGRAM_TOKEN не настроен. Бот не работает.")
    
    app.run(host='0.0.0.0', port=PORT)
