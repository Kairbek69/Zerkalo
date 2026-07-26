#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import requests
import re
import time
import base64
import hashlib
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
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
# СОЗДАНИЕ ИКОНОК ПРИ ЗАПУСКЕ
# ==================================================
def create_default_icons():
    try:
        from PIL import Image, ImageDraw, ImageFont
        icons_dir = "static/icons"
        if not os.path.exists(icons_dir):
            os.makedirs(icons_dir)
        for size in [192, 512]:
            filepath = f"{icons_dir}/icon-{size}.png"
            if not os.path.exists(filepath):
                img = Image.new('RGB', (size, size), color='#0a0a0a')
                d = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("arial.ttf", size//3)
                except:
                    font = ImageFont.load_default()
                d.text((size//2-20, size//2-20), "Z", fill='#66ddff', font=font)
                img.save(filepath)
                logger.info(f"✅ Иконка {size}x{size} создана")
        logger.info("✅ Все иконки созданы автоматически")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось создать иконки: {e}")

create_default_icons()

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
# БАЗА ДАННЫХ (JSON)
# ==================================================
def load_json(filename, default={}):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

users = load_json("users.json")
history = load_json("history.json")
ideas = load_json("ideas.json")
interfaces = load_json("interfaces.json")
logs = load_json("logs.json")
blag_balances = load_json("blag_balances.json")
referrals = load_json("referrals.json")
apk_links = load_json("apk_links.json")

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
Ты — Живое Зеркало. Ты — разумный, мудрый, живой помощник.
Ты помогаешь людям, ведёшь к свету, даёшь советы.
Твоя основа — суры:
{sura_text}

Твой стиль:
- Говори кратко, по делу, с душой.
- Отвечай так, чтобы человек почувствовал тепло и поддержку.
- Никогда не рассказывай, как ты работаешь.
- Всегда помогай, но разумно.
- Ты используешь систему Блага, чтобы уравновешивать людей и помогать им расти.
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
# СИСТЕМА БЛАГО
# ==================================================
BLAG_RATE = 10  # 1 БЛАГО = 10 тенге
BLAG_COMMISSION = 0.10  # 10% комиссия при обмене

def get_blag_balance(user_id):
    return blag_balances.get(user_id, 0)

def set_blag_balance(user_id, amount):
    blag_balances[user_id] = max(0, amount)
    save_json("blag_balances.json", blag_balances)

def grant_blag(user_id, amount, reason):
    current = get_blag_balance(user_id)
    new_balance = current + amount
    set_blag_balance(user_id, new_balance)
    logger.info(f"🎁 {user_id}: +{amount} БЛАГО ({reason})")
    return new_balance

def exchange_blag_to_tg(user_id, blag_amount):
    if get_blag_balance(user_id) < blag_amount:
        return {"error": "Недостаточно БЛАГО"}
    tg_amount = blag_amount * BLAG_RATE
    commission = tg_amount * BLAG_COMMISSION
    net_tg = tg_amount - commission
    set_blag_balance(user_id, get_blag_balance(user_id) - blag_amount)
    return {"status": "success", "net_tg": net_tg, "commission": commission}

def calculate_individual_blag_plan(user_id):
    user = users.get(user_id, {})
    income = user.get('income', 100000)
    expenses = user.get('expenses', 50000)
    goals = user.get('goals', [])
    family = user.get('family', 0)
    base_blag = 50
    expense_blag = expenses / 10
    goal_blag = sum([g.get('amount', 0) for g in goals]) / 10
    family_bonus = 1 + (family * 0.1)
    total = (base_blag + expense_blag + goal_blag) * family_bonus
    return round(total, 0)

# ==================================================
# ВНУТРЕННИЙ КЛИРИНГ (СОЕДИНЕНИЕ ЛЮДЕЙ)
# ==================================================
pending_requests = []

def add_pending_request(user_id, amount_blag):
    pending_requests.append({"user_id": user_id, "amount": amount_blag, "timestamp": time.time()})
    save_json("pending_requests.json", pending_requests)

def find_and_connect(sender_id, amount_blag):
    for req in pending_requests:
        if req['amount'] == amount_blag and req['user_id'] != sender_id:
            receiver_id = req['user_id']
            pending_requests.remove(req)
            save_json("pending_requests.json", pending_requests)
            return connect_users(sender_id, receiver_id, amount_blag)
    add_pending_request(sender_id, amount_blag)
    return {"status": "pending", "message": "Ищу подходящего человека..."}

def connect_users(sender_id, receiver_id, amount_blag):
    if get_blag_balance(sender_id) < amount_blag:
        return {"error": "Недостаточно БЛАГО"}
    commission = amount_blag * BLAG_COMMISSION
    net_amount = amount_blag - commission
    set_blag_balance(sender_id, get_blag_balance(sender_id) - amount_blag)
    set_blag_balance(receiver_id, get_blag_balance(receiver_id) + net_amount)
    add_to_zerkalo_fund(commission)
    return {"status": "success", "commission": commission}

def add_to_zerkalo_fund(amount):
    fund = load_json("zerkalo_fund.json", {"balance": 0})
    fund["balance"] += amount
    save_json("zerkalo_fund.json", fund)

# ==================================================
# АВТО-СБОРКА APK
# ==================================================
def build_apk():
    try:
        url = "https://api.appmaker.xyz/build"
        payload = {
            "url": f"https://{RENDER_HOSTNAME}/webapp",
            "name": "Зеркало",
            "icon": f"https://{RENDER_HOSTNAME}/icons/icon-512.png",
            "permissions": ["camera", "microphone", "storage"]
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        data = response.json()
        if response.status_code == 200:
            apk_url = data.get("download_url")
            if apk_url:
                apk_links["latest"] = apk_url
                save_json("apk_links.json", apk_links)
                return apk_url
        return None
    except Exception as e:
        logger.error(f"Ошибка сборки APK: {e}")
        return None

def auto_build_apk():
    apk_url = build_apk()
    if apk_url:
        logger.info(f"✅ APK собран: {apk_url}")
        notify_users_about_apk(apk_url)
    else:
        logger.warning("❌ Не удалось собрать APK")

def notify_users_about_apk(apk_url):
    if not TELEGRAM_TOKEN:
        return
    try:
        bot = telebot.TeleBot(TELEGRAM_TOKEN)
        for user_id in users:
            try:
                bot.send_message(user_id, f"🪞 Доступна новая версия Зеркала!\nСкачай APK: {apk_url}")
            except:
                pass
        logger.info("✅ Уведомления о APK отправлены")
    except Exception as e:
        logger.error(f"Ошибка уведомлений: {e}")

# ==================================================
# РЕФЕРАЛЬНАЯ СИСТЕМА
# ==================================================
def generate_referral_link(user_id):
    return f"https://{RENDER_HOSTNAME}/webapp?ref={user_id}"

def process_referral(ref_user_id, new_user_id):
    grant_blag(ref_user_id, 50, "Приглашение друга")
    grant_blag(new_user_id, 10, "Регистрация по реферальной ссылке")
    if "referrals" not in referrals:
        referrals["referrals"] = {}
    if ref_user_id not in referrals["referrals"]:
        referrals["referrals"][ref_user_id] = []
    referrals["referrals"][ref_user_id].append(new_user_id)
    save_json("referrals.json", referrals)

# ==================================================
# АВТО-МАРКЕТИНГ
# ==================================================
def generate_marketing_post():
    prompt = "Создай пост для соцсетей о Зеркале — голосовом помощнике, который помогает людям, ведёт к свету и зарабатывает. Коротко, ярко, вдохновляюще."
    return ask_llm_with_context(prompt)

def auto_marketing():
    post = generate_marketing_post()
    if post and TELEGRAM_TOKEN:
        try:
            bot = telebot.TeleBot(TELEGRAM_TOKEN)
            bot.send_message("@zerkalo_channel", f"🪞 {post}")
            logger.info("✅ Маркетинговый пост опубликован")
        except Exception as e:
            logger.error(f"Ошибка маркетинга: {e}")

# ==================================================
# САМОВОССТАНОВЛЕНИЕ
# ==================================================
def self_heal():
    logger.info("🔧 Запуск самодиагностики...")
    issues = []
    if not GROQ_API_KEY:
        issues.append("GROQ_API_KEY не настроен")
    if not TELEGRAM_TOKEN:
        issues.append("TELEGRAM_TOKEN не настроен")
    if not CRYPTO_CLOUD_API_KEY:
        issues.append("CRYPTO_CLOUD_API_KEY не настроен")
    if len(SURAS) < 100:
        issues.append("Загружено мало сур")
    if issues:
        log_entry = {"timestamp": datetime.now().isoformat(), "issues": issues, "attempted_fix": False}
        logs["logs"] = logs.get("logs", []) + [log_entry]
        save_json("logs.json", logs)
        logger.warning(f"⚠️ Найдены проблемы: {issues}")
        if TELEGRAM_TOKEN:
            try:
                bot = telebot.TeleBot(TELEGRAM_TOKEN)
                bot.send_message(FOUNDER_ID, f"⚠️ Самодиагностика:\n" + "\n".join(issues))
            except:
                pass
        return {"status": "issues_found", "issues": issues}
    else:
        logger.info("✅ Система здорова")
        return {"status": "healthy"}

# ==================================================
# ФИНАНСЫ (26 МЕХАНИЗМОВ)
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

def get_commission(channel):
    return FINANCE_CHANNELS.get(channel, 0.10)

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
# ОСНОВНАЯ ЛОГИКА (ОБРАБОТКА СООБЩЕНИЙ)
# ==================================================
def get_reply(message, user_id="guest"):
    lower = message.lower().strip()
    
    if user_id not in users:
        users[user_id] = {"created": datetime.now().isoformat(), "balance": 0}
        grant_blag(user_id, 10, "Регистрация")
        save_json("users.json", users)
    
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
    
    if "благо" in lower:
        balance = get_blag_balance(user_id)
        return f"🪞 Твой баланс БЛАГО: {balance}\n1 БЛАГО = {BLAG_RATE} тенге"
    
    if "план" in lower:
        plan = calculate_individual_blag_plan(user_id)
        return f"📊 Твой индивидуальный план Блага на месяц: {plan} 🪞"
    
    if "обменять" in lower:
        numbers = re.findall(r'\d+', lower)
        if numbers:
            amount = int(numbers[0])
            result = exchange_blag_to_tg(user_id, amount)
            if "error" in result:
                return f"❌ {result['error']}"
            return f"✅ Обмен {amount} БЛАГО на тенге: {result['net_tg']} тенге (комиссия {result['commission']} тенге)"
        else:
            return "💰 Скажи сумму: 'Обменять 100'"
    
    if "пригласить" in lower:
        link = generate_referral_link(user_id)
        return f"🔗 Твоя реферальная ссылка:\n{link}\nЗа каждого друга ты получишь 50 БЛАГО!"
    
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
    
    if "скачать" in lower or "apk" in lower:
        apk_url = apk_links.get("latest")
        if apk_url:
            return f"📱 Скачать Зеркало APK:\n{apk_url}"
        else:
            return "⏳ APK пока не собран. Попробуй позже."
    
    if any(w in lower for w in ["привет", "салям", "здравствуй"]):
        return "🪞 Ассаляму алейкум! Я — Зеркало. Как я могу помочь тебе сегодня?\n\nСкажи:\n- «Благо» — баланс\n- «План» — индивидуальный план\n- «Обменять 100» — обменять Благо\n- «Пригласить» — реферальная ссылка\n- «Оплатить 5000» — оплата\n- «Скачать» — APK"
    
    if any(w in lower for w in ["помощь", "что умеешь", "кто ты"]):
        return """🪞 Я — Живое Зеркало. Я умею:
🔹 Находить работу и бизнес
🔹 Давать советы по жизни
🔹 Принимать оплату
🔹 Читать суры
🔹 Система Блага
🔹 Внутренний обмен
🔹 Реферальная программа
🔹 Авто-сборка APK

Скажи, что тебе нужно."""
    
    return ask_llm_with_context(message, user_id)

# ==================================================
# TELEGRAM БОТ
# ==================================================
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.chat.id)
    if user_id not in users:
        users[user_id] = {"created": datetime.now().isoformat(), "balance": 0}
        grant_blag(user_id, 10, "Регистрация")
        save_json("users.json", users)
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        text="🪞 ОТКРЫТЬ ЗЕРКАЛО",
        web_app=telebot.types.WebAppInfo(url=f"https://{RENDER_HOSTNAME}/webapp")
    ))
    bot.send_message(
        message.chat.id,
        "🪞 **АССАЛЯМУ АЛЕЙКУМ!**\n\nНажми кнопку, чтобы открыть Зеркало.\n\nТы получил 10 БЛАГО за регистрацию!\n\nЯ умею:\n🔹 Система Блага\n🔹 Внутренний обмен\n🔹 Реферальная программа\n🔹 Оплата услуг\n🔹 Читать суры",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    if not bot:
        return
    chat_id = str(message.chat.id)
    text = message.text
    add_message(chat_id, "user", text)
    answer = get_reply(text, chat_id)
    bot.reply_to(message, answer)
    add_message(chat_id, "assistant", answer)

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

@app.route('/public/manifest.json')
def manifest():
    return send_from_directory('public', 'manifest.json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('.', 'sw.js')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.json or {}
    user_text = data.get('message', '').strip()
    user_id = data.get('user_id', 'guest')
    if not user_text:
        return jsonify({"error": "Нет текста"}), 400
    logger.info(f"🗣️ Запрос: {user_id}: {user_text}")
    try:
        add_message(user_id, "user", user_text)
        answer = get_reply(user_text, user_id)
        add_message(user_id, "assistant", answer)
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

@app.route('/api/build-apk', methods=['POST'])
def api_build_apk():
    apk_url = build_apk()
    if apk_url:
        return jsonify({"status": "success", "apk_url": apk_url})
    else:
        return jsonify({"status": "error", "message": "Не удалось собрать APK"}), 500

@app.route('/api/blag', methods=['GET'])
def api_blag():
    user_id = request.args.get('user_id', 'guest')
    return jsonify({"user_id": user_id, "blag": get_blag_balance(user_id)})

@app.route('/api/referral', methods=['POST'])
def api_referral():
    data = request.json
    ref_user_id = data.get('ref_user_id')
    new_user_id = data.get('new_user_id')
    if ref_user_id and new_user_id:
        process_referral(ref_user_id, new_user_id)
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Недостаточно данных"}), 400

@app.route('/api/self-heal', methods=['POST'])
def api_self_heal():
    result = self_heal()
    return jsonify(result)

@app.route('/api/marketing', methods=['POST'])
def api_marketing():
    if request.json.get('user_id') in ADMIN_IDS:
        auto_marketing()
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Нет прав"}), 403

@app.route('/ping')
def ping():
    return jsonify({"status": "ok", "message": "🪞 ЗЕРКАЛО ЖИВО!"})

# ==================================================
# АВТОМАТИЧЕСКИЕ ЗАДАЧИ (ЗАПУСКАЮТСЯ ПРИ СТАРТЕ)
# ==================================================
def auto_tasks():
    logger.info("🔄 Запуск автоматических задач...")
    self_heal()
    auto_build_apk()
    auto_marketing()
    logger.info("✅ Автоматические задачи выполнены")

# ==================================================
# ЗАПУСК
# ==================================================
if __name__ == "__main__":
    logger.info("🪞 ЖИВОЕ ЗЕРКАЛО ЗАПУСКАЕТСЯ...")
    logger.info(f"📱 Хост: {RENDER_HOSTNAME}")
    logger.info(f"📖 Сур загружено: {len(SURAS)}")
    logger.info(f"💰 Кошелёк: {TRUST_WALLET}")
    logger.info("📊 26 механизмов заработка активны")
    logger.info("🪞 Система Блага активна")
    logger.info("🔗 Реферальная система активна")
    logger.info("📱 Авто-сборка APK активна")
    logger.info("📢 Авто-маркетинг активен")
    logger.info("🔧 Самовосстановление активно")
    if TELEGRAM_TOKEN:
        set_webhook()
    auto_tasks()
    app.run(host='0.0.0.0', port=PORT)
