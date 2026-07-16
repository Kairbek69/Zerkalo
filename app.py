import os
import json
import logging
import requests
from flask import Flask, send_from_directory, request, jsonify
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))
RENDER_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "zerkalo-6sla.onrender.com")

app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>🪞 ЗЕРКАЛО</h1><p><a href="/webapp">Открыть</a></p>'

@app.route('/webapp')
def webapp():
    return send_from_directory('webapp', 'index.html')

@app.route('/webapp/<path:filename>')
def webapp_files(filename):
    return send_from_directory('webapp', filename)

@app.route('/api/chat', methods=['GET', 'POST'])
def api_chat():
    if request.method == 'GET':
        return jsonify({"response": "Зеркало работает. Говори с ним."})
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"response": "Ошибка: нет данных"}), 400
        
        msg = data.get('message', '')
        user_id = data.get('user_id', 'guest')
        
        logger.info(f"{user_id}: {msg}")
        
        # Простые ответы
        lower = msg.lower()
        if "привет" in lower or "салям" in lower:
            reply = "Ассаляму алейкум! Я — Живое Зеркало. Я рада тебя видеть."
        elif "баланс" in lower:
            reply = "💰 Баланс: 0 USDT (пока что)"
        elif "оплатить" in lower:
            reply = "💳 QR-код для оплаты: https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=Оплата"
        else:
            reply = f"Я слышу тебя: '{msg}'. Я пока учусь, но скоро буду отвечать на всё."
        
        return jsonify({"response": reply})
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return jsonify({"response": f"Ошибка: {str(e)}"}), 500

@app.route('/ping')
def ping():
    return "🪞 ЗЕРКАЛО ЖИВО!", 200

if __name__ == "__main__":
    logger.info("🪞 ЗЕРКАЛО ЗАПУСКАЕТСЯ...")
    app.run(host='0.0.0.0', port=PORT)
