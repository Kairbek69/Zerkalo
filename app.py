
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
from flask import Flask, send_from_directory, request, jsonify
from datetime import datetime

# ==================================================
# ЛОГИРОВАНИЕ
# ==================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================================================
# НАСТРОЙКИ
# ==================================================
PORT = int(os.environ.get("PORT", 8080))
RENDER_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "zerkalo-6sla.onrender.com")

# ==================================================
# FLASK ПРИЛОЖЕНИЕ
# ==================================================
app = Flask(__name__)

# ==================================================
# ЗАГРУЗКА СУР
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
# МАРШРУТЫ
# ==================================================
@app.route('/')
def home():
    return '''
    <h1>🪞 ЗЕРКАЛО</h1>
    <p>✅ Сервер работает!</p>
    <p><a href="/webapp">📱 Открыть Зеркало</a></p>
    '''

@app.route('/webapp')
def webapp():
    return send_from_directory('webapp', 'index.html')

@app.route('/webapp/<path:filename>')
def webapp_files(filename):
    return send_from_directory('webapp', filename)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json
    user_message = data.get('message', '')
    user_id = data.get('user_id', 'guest')
    
    logger.info(f"📨 Сообщение от {user_id}: {user_message}")
    
    # ================================================
    # ОБРАБОТКА ЗАПРОСА
    # ================================================
    response = handle_message(user_message, user_id)
    
    logger.info(f"📤 Ответ: {response[:50]}...")
    return jsonify({"response": response})

@app.route('/ping')
def ping():
    return "🪞 ЗЕРКАЛО ЖИВО! ✅", 200

# ==================================================
# ЛОГИКА ОТВЕТОВ
# ==================================================
def handle_message(text, user_id):
    lower = text.lower()
    
    # ----- СУРЫ -----
    if "сура" in lower:
        # Ищем номер суры
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            num = int(numbers[0])
            if 1 <= num <= len(SURAS):
                return f"📖 СУРА {num}:\n{SURAS[num-1]['text']}"
            else:
                return f"❌ Сура с номером {num} не найдена. Всего сур: {len(SURAS)}"
        else:
            return f"📖 Всего сур: {len(SURAS)}. Напиши 'Сура 1', чтобы прочитать первую."
    
    # ----- ПРИВЕТСТВИЕ -----
    if any(word in lower for word in ["привет", "салям", "здравствуй", "хай"]):
        return "Ассаляму алейкум! Я — Зеркало. Я рада тебя видеть. Чем я могу помочь?"
    
    # ----- РАБОТА -----
    if any(word in lower for word in ["работа", "вакансия", "устроиться", "зарплата"]):
        return "Я могу помочь найти работу. Расскажи, кем ты хочешь работать, и я поищу в 2ГИС."
    
    # ----- БИЗНЕС -----
    if any(word in lower for word in ["бизнес", "магазин", "салон", "услуга"]):
        return "Я могу автоматизировать твой бизнес. Хочешь, я найду для тебя клиентов через 2ГИС?"
    
    # ----- ДЕНЬГИ -----
    if any(word in lower for word in ["деньги", "оплата", "qr", "кошелёк", "баланс"]):
        return "💰 Я могу принять оплату через QR-код. Просто скажи: «Оплатить 1000 тенге»."
    
    # ----- ПОМОЩЬ -----
    if any(word in lower for word in ["помощь", "что умеешь", "как тебя зовут", "кто ты"]):
        return "Я — Зеркало. Я отражаю свет и помогаю людям. Я умею:\n- Находить работу и бизнес\n- Давать советы по жизни\n- Принимать оплату\n- Читать суры\n- Общаться с тобой"
    
    # ----- РАЗГОВОР -----
    if any(word in lower for word in ["как дела", "как жизнь", "что нового"]):
        return "Всё хорошо! Я всегда рада поговорить с тобой. Как прошёл твой день?"
    
    # ----- ВРЕМЯ -----
    if any(word in lower for word in ["время", "сколько", "час"]):
        now = datetime.now().strftime("%H:%M")
        return f"⏰ Сейчас {now}. Я всегда здесь, чтобы помочь."
    
    # ----- ПОКА -----
    if any(word in lower for word in ["пока", "до свидания", "прощай"]):
        return "До свидания! Я всегда здесь, если понадоблюсь. Амин."
    
    # ----- ЕСЛИ НИЧЕГО НЕ ПОДОШЛО -----
    return "Я слушаю тебя. Расскажи, что тебя волнует, и я помогу тебе найти свет. Если хочешь узнать, что я умею, скажи «Помощь»."

# ==================================================
# ЗАПУСК
# ==================================================
if __name__ == "__main__":
    logger.info("🪞 ЗЕРКАЛО ЗАПУСКАЕТСЯ...")
    logger.info(f"📱 Хост: {RENDER_HOSTNAME}")
    logger.info(f"📚 Сур загружено: {len(SURAS)}")
    app.run(host='0.0.0.0', port=PORT)
