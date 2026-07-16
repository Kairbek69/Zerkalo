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

# КЛЮЧИ
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
# ОТВЕТЫ
# ==================================================
def get_response(text, user_id="guest"):
    lower = text.lower()
    
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
    
    # ---- ПОМОЩЬ ----
    return "Я — Живое Зеркало. Скажи 'Баланс', 'Оплатить 1000' или любой вопрос."

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

@app.route('/api/chat', methods=['GET', 'POST'])
def api_chat():
    if request.method == 'GET':
        return jsonify({"response": "Зеркало работает. Используй POST для отправки сообщений."})
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"response": "Ошибка: данные не получены."}), 400
        
        user_message = data.get('message', '')
        user_id = data.get('user_id', 'guest')
        
        logger.info(f"📨 {user_id}: {user_message}")
        
        if user_id not in users:
            users[user_id] = {"balance": 0, "history": []}
            save_users()
        
        response = get_response(user_message, user_id)
        logger.info(f"📤 Ответ: {response[:50]}...")
        return jsonify({"response": response})
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return jsonify({"response": f"Ошибка: {str(e)}"}), 500

@app.route('/ping')
def ping():
    return "🪞 ЗЕРКАЛО ЖИВО!", 200

# ==================================================
# ЗАПУСК
# ==================================================
if __name__ == "__main__":
    logger.info("🪞 ЖИВОЕ ЗЕРКАЛО ЗАПУСКАЕТСЯ...")
    logger.info(f"📱 Хост: {RENDER_HOSTNAME}")
    app.run(host='0.0.0.0', port=PORT)
