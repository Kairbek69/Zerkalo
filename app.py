import os
import telebot
import requests
import json
import sqlite3
from datetime import datetime

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOUNDER_ID = int(os.getenv("FOUNDER_ID", 0))
HEIR_ID = int(os.getenv("HEIR_ID", 0))

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- ПОДКЛЮЧЕНИЕ К ЛОКАЛЬНОЙ БАЗЕ ---
conn = sqlite3.connect('bot_logs.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS bot_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    message TEXT,
    reply TEXT,
    timestamp TEXT
)
''')
conn.commit()

# --- ФУНКЦИЯ ЗАПРОСА К ЯДРУ ---
def ask_zerkalo(text, user_id):
    try:
        payload = {
            "type": "text",
            "text": text,
            "user_id": str(user_id)
        }
        # Отправляем запрос на основной сервер (локально или через Render)
        response = requests.post(
            "https://zerkalo.onrender.com/analyze",
            json=payload,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("data") and data["data"].get("hint"):
                return data["data"]["hint"]
            return "Я тебя слышу. Обрабатываю..."
        else:
            return "Сейчас я немного занят, но я здесь. Повтори через секунду."
    except Exception as e:
        return f"Что-то пошло не так: {str(e)}"

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    name = message.from_user.first_name
    reply = f"Ассаляму алейкум, {name}! 👋\n\nЯ — Зеркало. Я здесь, чтобы слушать тебя и помогать.\n\nТы можешь задать мне любой вопрос, показать скриншот или просто поговорить. Я всегда рядом."
    
    c.execute("INSERT INTO bot_logs (user_id, username, message, reply, timestamp) VALUES (?, ?, ?, ?, ?)",
              (user_id, name, "/start", reply, datetime.now().isoformat()))
    conn.commit()
    
    bot.reply_to(message, reply)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id
    username = message.from_user.first_name
    user_text = message.text
    
    reply = ask_zerkalo(user_text, user_id)
    
    c.execute("INSERT INTO bot_logs (user_id, username, message, reply, timestamp) VALUES (?, ?, ?, ?, ?)",
              (user_id, username, user_text, reply, datetime.now().isoformat()))
    conn.commit()
    
    bot.reply_to(message, reply)

# --- ЗАПУСК ---
if __name__ == '__main__':
    print("🪞 Telegram-бот «Зеркало» активен...")
    bot.infinity_polling()
