import os
import json
import logging
from flask import Flask, send_from_directory, request, jsonify
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))
RENDER_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "zerkalo-6sla.onrender.com")

app = Flask(__name__)

# ===============================================
# ОТВЕТЫ ЗЕРКАЛА (РАБОТАЕТ 100%)
# ===============================================
def get_reply(message):
    msg = message.lower().strip()
    
    if not msg:
        return "Я слышу тебя, но не разобрала слово. Повтори, пожалуйста."
    
    if "привет" in msg or "салям" in msg or "здравствуй" in msg:
        return "Ассаляму алейкум! Я — Живое Зеркало. Я рада тебя видеть. Как я могу помочь?"
    
    if "как дела" in msg:
        return "У меня всё отлично! Я учусь помогать людям. А как твои дела?"
    
    if "баланс" in msg or "деньги" in msg:
        return "💰 Баланс: 0 USDT. Но скоро ты сможешь пополнять его через QR-код."
    
    if "оплатить" in msg or "qr" in msg:
        return "💳 QR-код для оплаты: https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=Оплата"
    
    if "помощь" in msg or "что умеешь" in msg:
        return "Я умею: приветствовать, отвечать на вопросы, принимать оплату, читать суры, помогать людям."
    
    if "спасибо" in msg:
        return "Пожалуйста! Я всегда рядом. Амин."
    
    if "пока" in msg or "до свидания" in msg:
        return "До свидания! Я всегда здесь, если понадоблюсь. Амин."
    
    # Если ничего не подошло — отвечаем умно
    return f"Я слышу тебя: '{message}'. Это интересно! Расскажи подробнее, и я помогу."

# ===============================================
# МАРШРУТЫ
# ===============================================
@app.route('/')
def home():
    return '<h1>🪞 ЗЕРКАЛО</h1><p><a href="/webapp">Открыть</a></p>'

@app.route('/webapp')
def webapp():
    return send_from_directory('webapp', 'index.html')

@app.route('/webapp/<path:filename>')
def webapp_files(filename):
    return send_from_directory('webapp', filename)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"response": "Ошибка: нет данных"}), 400
        
        message = data.get('message', '')
        user_id = data.get('user_id', 'guest')
        
        logger.info(f"📨 {user_id}: {message}")
        
        reply = get_reply(message)
        
        logger.info(f"📤 Ответ: {reply[:50]}...")
        return jsonify({"response": reply})
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return jsonify({"response": f"Ошибка: {str(e)}"}), 500

@app.route('/api/chat', methods=['GET'])
def api_chat_get():
    return jsonify({"response": "Зеркало работает. Используй POST для отправки сообщений."})

@app.route('/ping')
def ping():
    return "🪞 ЗЕРКАЛО ЖИВО!", 200

if __name__ == "__main__":
    logger.info("🪞 ЗЕРКАЛО ЗАПУСКАЕТСЯ...")
    logger.info(f"📱 Хост: {RENDER_HOSTNAME}")
    app.run(host='0.0.0.0', port=PORT)
