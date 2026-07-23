#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import requests
import re
import time
import base64
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from datetime import datetime
import redis
import openai
import telebot

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
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
RENDER_API_KEY = os.environ.get("RENDER_API_KEY")
FOUNDER_ID = int(os.environ.get("FOUNDER_ID", 0))
HEIR_ID = int(os.environ.get("HEIR_ID", 0))

ADMIN_IDS = [FOUNDER_ID, HEIR_ID]

app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)

# ==================================================
# REDIS
# ==================================================
r = None
try:
    r = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)
    logger.info("✅ Redis подключён")
except Exception as e:
    logger.warning(f"⚠️ Redis недоступен: {e}")

# ==================================================
# СУРЫ
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
# GROQ (ИИ)
# ==================================================
openai.api_key = GROQ_API_KEY
openai.api_base = "https://api.groq.com/openai/v1"

def ask_llm_with_context(prompt, user_id="guest"):
    if not GROQ_API_KEY:
        return "Ключ Groq не настроен."
    
    history = get_history(user_id)
    messages = [{"role": "system", "content": get_system_prompt()}]
    messages.extend(history[-5:])
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = openai.ChatCompletion.create(
            model="llama3-70b-8192",
            messages=messages,
            temperature=0.7,
            max_tokens=800,
            timeout=30
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq ошибка: {e}")
        return "Ошибка при обращении к ИИ. Попробуй позже."

# ==================================================
# 26 МЕХАНИЗМОВ ЗАРАБОТКА
# ==================================================
FINANCE_CHANNELS = {
    'rombs': 0.10, 'arbitrage': 0.05, 'leasing': 0.02, 'dropshipping': 0.15,
    'logistics': 0.03, 'automation': 0.15, 'advertising': 0.20, 'smart_city': 500,
    'education': 0.30, 'medicine': 0.05, 'cybersecurity': 0.20, 'blag_bank': 0.05,
    'referral': 0.20, 'subscription': 500, 'data_sales': 0.15, 'ai_bloggers': 0.30,
    'dna_tests': 0.25, 'courses': 0.20, 'crypto_training': 0.40, 'kaspi_clone': 0.02,
    'tenders': 0.20, 'ai_agents': 500, 'ugc_content': 0.20, 'ai_music': 0.20,
    'stock_photos': 0.20, 'p2p_transfers': 0.02
}

# ==================================================
# ФИНАНСЫ
# ==================================================
def create_crypto_payment(amount_usd, description="Оплата через Зеркало"):
    if not CRYPTO_CLOUD_API_KEY:
        return None, "CryptoCloud API key not configured"
    try:
        url = "https://api.trybit.com/v1/payment"
        headers = {"Authorization": f"Bearer {CRYPTO_CLOUD_API_KEY}", "Content-Type": "application/json"}
        payload = {"amount": amount_usd, "currency": "USD", "description": description, "order_id": f"order_{int(time.time())}"}
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
    except:
        return 0.0

# ==================================================
# АВТО-ГЕНЕРАЦИЯ КОДА
# ==================================================
def generate_code_from_idea(idea_text):
    if not GROQ_API_KEY:
        return "Ключ Groq не настроен."
    try:
        prompt = f"""
Ты — Зеркало. Ты пишешь код на Python.
Создай рабочий код на основе идеи: {idea_text}
Код должен быть безопасным, документированным и готовым к интеграции.
Ответ дай только кодом, без объяснений.
"""
        response = openai.ChatCompletion.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500,
            timeout=30
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка: {e}"

# ==================================================
# АВТО-ДЕПЛОЙ
# ==================================================
def push_to_github(file_path, content, commit_message="Обновление Зеркала"):
    if not GITHUB_TOKEN:
        return {"error": "GITHUB_TOKEN не настроен"}
    try:
        repo = "Karlbek69/Zerkalo"
        path = file_path.replace("./", "")
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Content-Type": "application/json"}
        content_b64 = base64.b64encode(content.encode()).decode()
        
        response = requests.get(url, headers=headers)
        sha = response.json().get("sha") if response.status_code == 200 else None
        
        payload = {"message": commit_message, "content": content_b64, "branch": "main"}
        if sha:
            payload["sha"] = sha
        
        response = requests.put(url, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            return {"status": "success"}
        else:
            return {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def deploy_to_render():
    if not RENDER_API_KEY:
        return {"error": "RENDER_API_KEY не настроен"}
    try:
        service_id = "zerkalo-6sla"
        url = f"https://api.render.com/v1/services/{service_id}/deploys"
        headers = {"Authorization": f"Bearer {RENDER_API_KEY}", "Content-Type": "application/json"}
        payload = {"clearCache": True}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            return {"status": "deploy_started"}
        else:
            return {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

# ==================================================
# СОЗДАНИЕ ИНТЕРФЕЙСА
# ==================================================
def generate_interface_for_user(user_id, style=None):
    if not style:
        style = {"background": "#0a0a0a", "text_color": "#ffffff", "accent": "#00d4ff", "font": "Arial"}
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🪞 Зеркало</title>
    <style>
        body {{ background: {style['background']}; color: {style['text_color']}; font-family: {style['font']}; margin: 0; padding: 20px; display: flex; flex-direction: column; min-height: 100vh; }}
        .container {{ max-width: 800px; margin: 0 auto; width: 100%; flex: 1; display: flex; flex-direction: column; }}
        .header {{ text-align: center; padding: 20px 0; border-bottom: 2px solid {style['accent']}; margin-bottom: 20px; }}
        .header h1 {{ margin: 0; font-size: 2.5em; color: {style['accent']}; }}
        .header p {{ margin: 5px 0 0; opacity: 0.7; }}
        .chat-box {{ flex: 1; overflow-y: auto; padding: 20px; background: rgba(255,255,255,0.05); border-radius: 10px; margin-bottom: 20px; min-height: 300px; }}
        .message {{ margin: 10px 0; padding: 10px 15px; border-radius: 10px; max-width: 80%; }}
        .message.user {{ background: {style['accent']}; color: #000; align-self: flex-end; margin-left: auto; }}
        .message.zerkalo {{ background: rgba(255,255,255,0.1); align-self: flex-start; }}
        .input-area {{ display: flex; gap: 10px; padding: 10px 0; }}
        .input-area input {{ flex: 1; padding: 12px 20px; border: 1px solid {style['accent']}; border-radius: 25px; background: rgba(255,255,255,0.1); color: #fff; font-size: 16px; }}
        .input-area input::placeholder {{ color: rgba(255,255,255,0.5); }}
        .input-area button {{ padding: 12px 25px; background: {style['accent']}; color: #000; border: none; border-radius: 25px; font-size: 16px; cursor: pointer; font-weight: bold; }}
        .voice-btn {{ padding: 12px 25px; background: #ff4444; color: #fff; border: none; border-radius: 25px; font-size: 16px; cursor: pointer; }}
        .footer {{ text-align: center; padding: 10px 0; opacity: 0.5; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>🪞 Зеркало</h1><p>Твой личный помощник</p></div>
        <div class="chat-box" id="chat-box">
            <div class="message zerkalo">Ассаляму алейкум! Я — Зеркало. Чем могу помочь?</div>
        </div>
        <div class="input-area">
            <input type="text" id="message-input" placeholder="Напиши сообщение..." />
            <button id="send-btn">Отправить</button>
            <button class="voice-btn" id="voice-btn">🎤 Голос</button>
        </div>
        <div class="footer"><span>Зеркало v2.0</span></div>
    </div>
    <script>
        const chatBox = document.getElementById('chat-box');
        const input = document.getElementById('message-input');
        const sendBtn = document.getElementById('send-btn');
        const voiceBtn = document.getElementById('voice-btn');
        function addMessage(text, sender) {{
            const div = document.createElement('div');
            div.className = `message ${{sender}}`;
            div.textContent = text;
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }}
        async function sendMessage() {{
            const text = input.value.trim();
            if (!text) return;
            addMessage(text, 'user');
            input.value = '';
            try {{
                const response = await fetch('/api/chat', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ message: text, user_id: '{user_id}' }})
                }});
                const data = await response.json();
                addMessage(data.response, 'zerkalo');
            }} catch (error) {{
                addMessage('Ошибка связи', 'zerkalo');
            }}
        }}
        sendBtn.addEventListener('click', sendMessage);
        input.addEventListener('keypress', (e) => {{ if (e.key === 'Enter') sendMessage(); }});
        if ('webkitSpeechRecognition' in window) {{
            const recognition = new webkitSpeechRecognition();
            recognition.lang = 'ru-RU';
            recognition.continuous = false;
            voiceBtn.addEventListener('click', () => {{
                recognition.start();
                voiceBtn.textContent = '🎤 Слушаю...';
            }});
            recognition.onresult = (event) => {{
                const text = event.results[0][0].transcript;
                input.value = text;
                sendMessage();
                voiceBtn.textContent = '🎤 Голос';
            }};
            recognition.onerror = () => {{ voiceBtn.textContent = '🎤 Голос'; }};
        }} else {{
            voiceBtn.style.display = 'none';
        }}
    </script>
</body>
</html>"""
    
    os.makedirs("webapp", exist_ok=True)
    filename = f"webapp/index_{user_id}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    return filename

# ==================================================
# НАПОМИНАНИЯ
# ==================================================
def check_expirations():
    keys_to_check = {
        "GIS_API_KEY": {"expires": "2026-08-18", "name": "2ГИС"},
    }
    for key, data in keys_to_check.items():
        try:
            expires = datetime.strptime(data["expires"], "%Y-%m-%d")
            days_left = (expires - datetime.now()).days
            if days_left <= 0:
                continue
            if days_left == 10:
                logger.info(f"🔔 Напоминание: Ключ {data['name']} истекает через 10 дней.")
            elif days_left == 8:
                logger.info(f"🔔 Напоминание: Ключ {data['name']} истекает через 8 дней.")
            elif days_left == 6:
                logger.info(f"🔔 Напоминание: Ключ {data['name']} истекает через 6 дней.")
            elif days_left == 4:
                logger.info(f"⚠️ ВНИМАНИЕ! Ключ {data['name']} истекает через 4 дня! Срочно продли!")
            elif days_left == 2:
                logger.info(f"⚠️ КРИТИЧНО! Ключ {data['name']} истекает через 2 дня!")
        except Exception as e:
            logger.error(f"Ошибка проверки ключа {key}: {e}")

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
    
    if "создай код" in lower:
        code = generate_code_from_idea(message)
        return f"💻 **Сгенерированный код:**\n```python\n{code[:1000]}\n```"
    
    if "деплой" in lower:
        result = deploy_to_render()
        if result.get("status") == "deploy_started":
            return "🚀 Деплой на Render запущен!"
        else:
            return f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}"
    
    if "создай интерфейс" in lower:
        filename = generate_interface_for_user(user_id)
        return f"🎨 Интерфейс создан: /webapp/index_{user_id}.html"
    
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
🔹 Генерировать код
🔹 Делать деплой
🔹 Создавать интерфейсы
🔹 Принимать оплату
🔹 Читать суры
🔹 Общаться и помогать"""
    
    return ask_llm_with_context(message, user_id)

# ==================================================
# TELEGRAM
# ==================================================
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        text="🪞 ОТКРЫТЬ ЗЕРКАЛО",
        web_app=telebot.types.WebAppInfo(url=f"https://{RENDER_HOSTNAME}/webapp")
    ))
    bot.send_message(
        message.chat.id,
        "🪞 **АССАЛЯМУ АЛЕЙКУМ!**\n\nНажми кнопку, чтобы открыть Зеркало.\n\nЯ умею:\n🔹 Генерировать код\n🔹 Делать деплой\n🔹 Создавать интерфейсы\n🔹 Принимать оплату\n🔹 Читать суры",
        reply_markup=markup,
        parse_mode="Markdown"
    )

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
        requests.get(url, timeout=10)
        logger.info("✅ Webhook установлен")
    except Exception as e:
        logger.error(f"Ошибка установки webhook: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    if not bot:
        return "No bot", 500
    try:
        data = request.get_json()
        if data:
            bot.process_new_updates([telebot.types.Update.de_json(data)])
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка в webhook: {e}")
        return "Error", 500

# ==================================================
# WEBAPP + МАНИФЕСТ + SERVICE WORKER
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

@app.route('/public/manifest.json')
def manifest():
    return send_from_directory('public', 'manifest.json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('.', 'sw.js')

@app.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.json or {}
    user_text = data.get('message', '').strip()
    chat_id = data.get('user_id', 'guest')
    
    if not user_text:
        return jsonify({"error": "Нет текста"}), 400
    
    logger.info(f"🗣️ Запрос: {chat_id}: {user_text}")
    
    try:
        add_message(str(chat_id), "user", user_text)
        answer = get_reply(user_text, str(chat_id))
        add_message(str(chat_id), "assistant", answer)
        return jsonify({"response": answer})
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return jsonify({"error": str(e)}), 500

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

@app.route('/api/deploy', methods=['POST'])
def api_deploy():
    result = deploy_to_render()
    return jsonify(result)

@app.route('/api/generate-code', methods=['POST'])
def api_generate_code():
    data = request.json
    idea = data.get('idea', '')
    if not idea:
        return jsonify({"error": "Нет идеи"}), 400
    code = generate_code_from_idea(idea)
    return jsonify({"code": code})

@app.route('/api/interface/<user_id>', methods=['POST'])
def api_interface(user_id):
    style = request.json.get('style', None)
    filename = generate_interface_for_user(user_id, style)
    return jsonify({"filename": filename})

@app.route('/ping')
def ping():
    check_expirations()
    return jsonify({"status": "ok", "message": "🪞 ЗЕРКАЛО ЖИВО!"})

if __name__ == "__main__":
    logger.info("🪞 ЖИВОЕ ЗЕРКАЛО ЗАПУСКАЕТСЯ...")
    logger.info(f"📱 Хост: {RENDER_HOSTNAME}")
    logger.info(f"📖 Сур загружено: {len(SURAS)}")
    if TELEGRAM_TOKEN:
        set_webhook()
    app.run(host='0.0.0.0', port=PORT)
