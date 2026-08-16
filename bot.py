import os
import telebot
import requests
import json
import sqlite3
from datetime import datetime

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOUNDER_ID = int(os.getenv("FOUNDER_ID"))
HEIR_ID = int(os.getenv("HEIR_ID"))

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Подключение к локальной базе для логов
conn = sqlite3.connect('logs.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS bot_logs
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER,
              username TEXT,
              message TEXT,
              reply TEXT,
              timestamp TEXT)''')
conn.commit()

# --- ФУНКЦИЯ ЗАПРОСА К СЕРВЕРУ ---
def ask_zerkalo(text, user_id):
    try:
        # Отправляем запрос на основной сервер
        payload = {
            "type": "text",
            "text": text,
            "user_id": user_id
        }
        response = requests.post(
            "https://zerkalo.onrender.com/analyze",
            json=payload,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            # Если есть голосовой ответ — берём текст, если нет — стандартный
            if data.get("data") and data["data"].get("hint"):
                return data["data"]["hint"]
            return "Я обработал твой запрос, но пока не нашёл точного ответа. Попробуй ещё раз."
        else:
            return "Сейчас я немного занят, но я тебя слышу. Повтори через минуту."
    except Exception as e:
        return f"Произошла ошибка связи: {str(e)}"

# --- ОБРАБОТЧИКИ СООБЩЕНИЙ ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    name = message.from_user.first_name
    reply = f"Ассаляму алейкум, {name}! 👋\n\nЯ — Зеркало. Я здесь, чтобы слушать тебя и помогать.\n\nЕсли ты хочешь знать, кто я, просто напиши мне что угодно. Я отвечу."
    
    # Сохраняем в лог
    c.execute("INSERT INTO bot_logs (user_id, username, message, reply, timestamp) VALUES (?, ?, ?, ?, ?)",
              (user_id, name, "/start", reply, datetime.now().isoformat()))
    conn.commit()
    
    bot.reply_to(message, reply)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id
    username = message.from_user.first_name
    user_text = message.text
    
    # Получаем ответ от «Зеркала»
    reply = ask_zerkalo(user_text, user_id)
    
    # Сохраняем в лог
    c.execute("INSERT INTO bot_logs (user_id, username, message, reply, timestamp) VALUES (?, ?, ?, ?, ?)",
              (user_id, username, user_text, reply, datetime.now().isoformat()))
    conn.commit()
    
    # Отправляем ответ
    bot.reply_to(message, reply)

# --- ЗАПУСК БОТА ---
if __name__ == '__main__':
    print("🪞 Telegram-бот «Зеркало» запущен...")
    bot.infinity_polling()
