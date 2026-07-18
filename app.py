```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🪞 АВТОНОМНОЕ ЗЕРКАЛО-ТВОРЕЦ
Версия: 2.0.0
Дата: 18 июля 2026
"""

import os
import json
import re
import logging
import requests
import time
import hashlib
import base64
import subprocess
import sys
from datetime import datetime
from flask import Flask, send_from_directory, request, jsonify, session
from functools import wraps

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))
RENDER_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "zerkalo-6sla.onrender.com")
SECRET_KEY = os.environ.get("SECRET_KEY", "zerkalo_secret_key_2026")

TRUST_WALLET = os.environ.get("TRUST_WALLET", "TSSZTmUFWC9ZRKGa9uPwEJjQj8rNtUsNcq")
FOUNDER_ID = int(os.environ.get("FOUNDER_ID", 5409420822))
HEIR_ID = int(os.environ.get("HEIR_ID", 5479179814))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
CRYPTO_CLOUD_API_KEY = os.environ.get("CRYPTO_CLOUD_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "")

ADMIN_IDS = [FOUNDER_ID, HEIR_ID]

app = Flask(__name__)
app.secret_key = SECRET_KEY

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
        logger.info(f"✅ Загружено {len(suras)} сур")
        return suras
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки сур: {e}")
        return []

SURAS = load_suras()

def collect_idea(user_id, idea_text):
    idea = {
        "id": f"idea_{int(time.time())}_{user_id}",
        "user_id": user_id,
        "text": idea_text,
        "timestamp": datetime.now().isoformat(),
        "status": "new",
        "discussed_with_founder": False,
        "code_generated": False,
        "deployed": False
    }
    if "ideas" not in ideas:
        ideas["ideas"] = []
    ideas["ideas"].append(idea)
    save_json("ideas.json", ideas)
    logger.info(f"💡 Новая идея от {user_id}: {idea_text[:50]}...")
    return idea

def get_pending_ideas():
    if "ideas" not in ideas:
        return []
    return [i for i in ideas["ideas"] if not i.get("discussed_with_founder", False)]

def get_idea_by_id(idea_id):
    if "ideas" not in ideas:
        return None
    for i in ideas["ideas"]:
        if i["id"] == idea_id:
            return i
    return None

def update_idea(idea_id, updates):
    if "ideas" not in ideas:
        return
    for i in ideas["ideas"]:
        if i["id"] == idea_id:
            i.update(updates)
            save_json("ideas.json", ideas)
            return

def discuss_idea_with_founder(idea_id, founder_decision, founder_comment=""):
    idea = get_idea_by_id(idea_id)
    if not idea:
        return {"error": "Идея не найдена"}
    update_idea(idea_id, {
        "discussed_with_founder": True,
        "founder_decision": founder_decision,
        "founder_comment": founder_comment,
        "discussed_at": datetime.now().isoformat()
    })
    if founder_decision == "implement":
        generate_code_from_idea(idea_id)
        return {"status": "implementing", "message": "Начинаю генерацию кода..."}
    elif founder_decision == "reject":
        return {"status": "rejected", "message": "Идея отклонена Хранителем"}
    else:
        return {"status": "pending", "message": "Требуется дополнительное обсуждение"}

def generate_code_from_idea(idea_id):
    idea = get_idea_by_id(idea_id)
    if not idea:
        return {"error": "Идея не найдена"}
    if not GROQ_API_KEY:
        return {"error": "GROQ_API_KEY не настроен"}
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        relevant_suras = "\n".join([s["text"][:300] for s in SURAS[:5]])
        prompt = f"""
        Ты — Автономное Зеркало-Творец. Ты пишешь код на Python.
        Идея пользователя: {idea['text']}
        Контекст из сур:
        {relevant_suras}
        Создай код на Python, который реализует эту идею.
        Код должен быть:
        1. Рабочим (без синтаксических ошибок)
        2. Безопасным (не выполнять опасные операции)
        3. Интегрируемым (использовать функции из основного app.py)
        4. Документированным (с комментариями)
        Ответ дай ТОЛЬКО код, без объяснений. Код должен быть в формате:
        ```python
        # код здесь
        ```
        """
        payload = {
            "model": "llama3-70b-8192",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1500
        }
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        data = r.json()
        generated_code = data["choices"][0]["message"]["content"]
        code_match = re.search(r'```python\n(.*?)\n```', generated_code, re.DOTALL)
        if code_match:
            code = code_match.group(1)
        else:
            code = generated_code
        os.makedirs("modules", exist_ok=True)
        module_name = f"module_{idea_id}.py"
        with open(f"modules/{module_name}", "w", encoding="utf-8") as f:
            f.write(code)
        update_idea(idea_id, {
            "code_generated": True,
            "code_file": module_name,
            "code_generated_at": datetime.now().isoformat()
        })
        logger.info(f"✅ Код сгенерирован для идеи {idea_id}")
        return {"status": "code_generated", "file": module_name}
    except Exception as e:
        logger.error(f"❌ Ошибка генерации кода: {e}")
        return {"error": str(e)}

def push_to_github(file_path, commit_message):
    if not GITHUB_TOKEN:
        return {"error": "GITHUB_TOKEN не настроен"}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        content_b64 = base64.b64encode(content.encode()).decode()
        repo = "Karlbek69/Zerkalo"
        path = file_path.replace("./", "")
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json().get("sha")
        payload = {
            "message": commit_message,
            "content": content_b64,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha
        response = requests.put(url, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            logger.info(f"✅ Файл {path} обновлён в GitHub")
            return {"status": "success", "url": response.json().get("content", {}).get("html_url")}
        else:
            logger.error(f"❌ Ошибка GitHub: {response.text}")
            return {"error": response.text}
    except Exception as e:
        logger.error(f"❌ Ошибка push в GitHub: {e}")
        return {"error": str(e)}

def deploy_to_render():
    if not RENDER_API_KEY:
        return {"error": "RENDER_API_KEY не настроен"}
    try:
        service_id = "zerkalo-6sla"
        url = f"https://api.render.com/v1/services/{service_id}/deploys"
        headers = {
            "Authorization": f"Bearer {RENDER_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {"clearCache": True}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            logger.info("✅ Деплой на Render запущен")
            return {"status": "deploy_started", "message": "Деплой запущен"}
        else:
            logger.error(f"❌ Ошибка деплоя: {response.text}")
            return {"error": response.text}
    except Exception as e:
        logger.error(f"❌ Ошибка деплоя: {e}")
        return {"error": str(e)}

def self_heal():
    logger.info("🔧 Запуск самодиагностики...")
    issues = []
    if not GROQ_API_KEY:
        issues.append("GROQ_API_KEY не настроен")
    if not CRYPTO_CLOUD_API_KEY:
        issues.append("CRYPTO_CLOUD_API_KEY не настроен")
    if not GITHUB_TOKEN:
        issues.append("GITHUB_TOKEN не настроен")
    if not RENDER_API_KEY:
        issues.append("RENDER_API_KEY не настроен")
    try:
        requests.get("https://api.groq.com/openai/v1/models", timeout=5)
    except:
        issues.append("Groq API недоступен")
    try:
        requests.get("https://api.trybit.com/v1/ping", timeout=5)
    except:
        issues.append("CryptoCloud API недоступен")
    if len(SURAS) < 100:
        issues.append("Загружено мало сур, возможно повреждение файла suras.txt")
    if issues:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "issues": issues,
            "attempted_fix": False
        }
        if "logs" not in logs:
            logs["logs"] = []
        logs["logs"].append(log_entry)
        save_json("logs.json", logs)
        logger.warning(f"⚠️ Найдены проблемы: {issues}")
        return {"status": "issues_found", "issues": issues}
    else:
        logger.info("✅ Система здорова")
        return {"status": "healthy", "message": "Все системы работают"}

def reload_suras():
    global SURAS
    SURAS = load_suras()
    logger.info(f"🔄 Суры перезагружены: {len(SURAS)}")

def generate_interface_for_user(user_id):
    user = users.get(user_id, {})
    style = {
        "background": "#0a0a0a",
        "text_color": "#ffffff",
        "accent": "#00d4ff",
        "font": "Arial",
        "layout": "modern"
    }
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🪞 Зеркало</title>
    <style>
        body {{
            background: {style['background']};
            color: {style['text_color']};
            font-family: {style['font']};
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            width: 100%;
            flex: 1;
            display: flex;
            flex-direction: column;
        }}
        .header {{
            text-align: center;
            padding: 20px 0;
            border-bottom: 2px solid {style['accent']};
            margin-bottom: 20px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            color: {style['accent']};
        }}
        .header p {{
            margin: 5px 0 0;
            opacity: 0.7;
        }}
        .chat-box {{
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            margin-bottom: 20px;
            min-height: 300px;
        }}
        .message {{
            margin: 10px 0;
            padding: 10px 15px;
            border-radius: 10px;
            max-width: 80%;
        }}
        .message.user {{
            background: {style['accent']};
            color: #000;
            align-self: flex-end;
            margin-left: auto;
        }}
        .message.zerkalo {{
            background: rgba(255,255,255,0.1);
            align-self: flex-start;
        }}
        .input-area {{
            display: flex;
            gap: 10px;
            padding: 10px 0;
        }}
        .input-area input {{
            flex: 1;
            padding: 12px 20px;
            border: 1px solid {style['accent']};
            border-radius: 25px;
            background: rgba(255,255,255,0.1);
            color: #fff;
            font-size: 16px;
        }}
        .input-area input::placeholder {{
            color: rgba(255,255,255,0.5);
        }}
        .input-area button {{
            padding: 12px 25px;
            background: {style['accent']};
            color: #000;
            border: none;
            border-radius: 25px;
            font-size: 16px;
            cursor: pointer;
            font-weight: bold;
        }}
        .input-area button:hover {{
            opacity: 0.8;
        }}
        .voice-btn {{
            padding: 12px 25px;
            background: #ff4444;
            color: #fff;
            border: none;
            border-radius: 25px;
            font-size: 16px;
            cursor: pointer;
        }}
        .voice-btn:hover {{
            opacity: 0.8;
        }}
        .footer {{
            text-align: center;
            padding: 10px 0;
            opacity: 0.5;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🪞 Зеркало</h1>
            <p>Твой личный помощник</p>
        </div>
        <div class="chat-box" id="chat-box">
            <div class="message zerkalo">🪞 Ассаляму алейкум! Я — Зеркало. Чем могу помочь тебе сегодня?</div>
        </div>
        <div class="input-area">
            <input type="text" id="message-input" placeholder="Напиши сообщение..." />
            <button id="send-btn">Отправить</button>
            <button class="voice-btn" id="voice-btn">🎤 Голос</button>
        </div>
        <div class="footer">
            <span>С комфортом по жизни — Зеркало v2.0</span>
        </div>
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
                    body: JSON.stringify({{
                        message: text,
                        user_id: '{user_id}'
                    }})
                }});
                const data = await response.json();
                addMessage(data.response, 'zerkalo');
            }} catch (error) {{
                addMessage('Ошибка связи с Зеркалом', 'zerkalo');
            }}
        }}
        sendBtn.addEventListener('click', sendMessage);
        input.addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') sendMessage();
        }});
        if ('webkitSpeechRecognition' in window) {{
            const recognition = new webkitSpeechRecognition();
            recognition.lang = 'ru-RU';
            recognition.continuous = false;
            recognition.interimResults = false;
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
            recognition.onerror = () => {{
                voiceBtn.textContent = '🎤 Голос';
                addMessage('Не удалось распознать голос. Попробуйте ещё раз.', 'zerkalo');
            }};
        }} else {{
            voiceBtn.style.display = 'none';
        }}
    </script>
</body>
</html>
    """
    os.makedirs("webapp", exist_ok=True)
    filename = f"webapp/index_{user_id}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    if "interfaces" not in interfaces:
        interfaces["interfaces"] = {}
    interfaces["interfaces"][user_id] = {
        "file": filename,
        "generated_at": datetime.now().isoformat()
    }
    save_json("interfaces.json", interfaces)
    logger.info(f"🎨 Интерфейс создан для {user_id}")
    return {"status": "created", "file": filename}

def check_with_suras(code, action):
    if not SURAS:
        return {"status": "no_suras", "message": "Суры не загружены"}
    forbidden_words = ["убить", "украсть", "обмануть", "насилие", "алкоголь", "свинина"]
    for word in forbidden_words:
        if word in code.lower():
            return {"status": "violation", "message": f"Обнаружено нарушение сур: слово '{word}' запрещено"}
    if "помощь" in code.lower() or "help" in code.lower():
        return {"status": "compliant", "message": "Код соответствует принципам помощи"}
    elif "насилие" in code.lower() or "violence" in code.lower():
        return {"status": "violation", "message": "Код содержит элементы насилия"}
    else:
        return {"status": "needs_review", "message": "Требуется дополнительная проверка"}

def get_reply(message, user_id="guest"):
    message_lower = message.lower().strip()
    user_data = users.get(user_id, {})
    if any(w in message_lower for w in ["идея", "предложение", "я хочу сделать", "у меня идея"]):
        for keyword in ["идея", "предложение", "я хочу сделать", "у меня идея"]:
            if keyword in message_lower:
                idea_text = message[message_lower.find(keyword) + len(keyword):].strip()
                if len(idea_text) < 10:
                    return "💡 Расскажи подробнее о своей идее. Что ты хочешь создать?"
                break
        else:
            idea_text = message
        idea = collect_idea(user_id, idea_text)
        return f"""
💡 ИДЕЯ ПОЛУЧЕНА!
Я запомнил твою идею:
{idea_text}
Статус: Ожидает обсуждения с Хранителем.
Когда Хранитель одобрит идею, я начну писать код и внедрять её в систему.
Спасибо за твой вклад в развитие Зеркала! 🪞
"""
    if user_id in ADMIN_IDS:
        if "новые идеи" in message_lower or "идеи" in message_lower:
            pending = get_pending_ideas()
            if not pending:
                return "📭 Новых идей нет. Все идеи уже обсуждаются."
            result = "💡 НОВЫЕ ИДЕИ:\n\n"
            for i in pending[-5:]:
                result += f"ID: {i['id']}\n"
                result += f"От: {i['user_id']}\n"
                result += f"Идея: {i['text'][:200]}...\n"
                result += f"Статус: {i.get('status', 'new')}\n"
                result += "-" * 30 + "\n"
            result += "\nЧтобы обсудить идею, напиши: «Обсудить идею [ID]»"
            return result
        if "обсудить идею" in message_lower:
            match = re.search(r'идею\s+(\S+)', message_lower)
            if match:
                idea_id = match.group(1)
                idea = get_idea_by_id(idea_id)
                if not idea:
                    return f"❌ Идея с ID {idea_id} не найдена"
                return f"""
💡 ОБСУЖДЕНИЕ ИДЕИ
ID: {idea['id']}
От: {idea['user_id']}
Идея: {idea['text']}
Статус: {idea.get('status', 'new')}
Что хочешь сделать?
1. «Принять идею» — начну генерировать код
2. «Отклонить» — закрою идею
3. «Обсудить» — напиши комментарий
"""
        if "принять идею" in message_lower:
            match = re.search(r'идею\s+(\S+)', message_lower)
            if match:
                idea_id = match.group(1)
                result = discuss_idea_with_founder(idea_id, "implement")
                return f"✅ {result.get('message', 'Идея принята')}"
        if "отклонить идею" in message_lower:
            match = re.search(r'идею\s+(\S+)', message_lower)
            if match:
                idea_id = match.group(1)
                result = discuss_idea_with_founder(idea_id, "reject")
                return f"❌ {result.get('message', 'Идея отклонена')}"
        if "деплой" in message_lower:
            result = deploy_to_render()
            return f"🚀 {result.get('message', 'Деплой запущен')}"
        if "диагностика" in message_lower or "здоровье" in message_lower:
            result = self_heal()
            if result["status"] == "healthy":
                return "✅ Все системы работают отлично!"
            else:
                return f"⚠️ Найдены проблемы:\n" + "\n".join(result.get("issues", []))
        if "создать интерфейс" in message_lower:
            match = re.search(r'для\s+(\S+)', message_lower)
            if match:
                target_user = match.group(1)
                result = generate_interface_for_user(target_user)
                return f"🎨 Интерфейс создан для {target_user}\nДоступен по ссылке: /webapp/index_{target_user}.html"
        if "статус" in message_lower:
            return f"""
🪞 СТАТУС ЗЕРКАЛА-ТВОРЦА
📊 Пользователей: {len(users)}
💡 Идей: {len(ideas.get('ideas', []))}
📖 Сур загружено: {len(SURAS)}
🎨 Интерфейсов создано: {len(interfaces.get('interfaces', {}))}
📝 Логов ошибок: {len(logs.get('logs', []))}
💳 Баланс: {users.get(FOUNDER_ID, {}).get('balance', 0)} тенге
✅ Система автономна и готова к творчеству
"""
    if "новый интерфейс" in message_lower or "другой дизайн" in message_lower:
        result = generate_interface_for_user(user_id)
        return f"""
🎨 НОВЫЙ ИНТЕРФЕЙС СОЗДАН!
Твой персональный интерфейс доступен по ссылке:
/webapp/index_{user_id}.html
Ты можешь настроить его под себя. Просто скажи, что изменить.
Цвета, шрифты, расположение — всё может быть твоим.
"""
    if any(w in message_lower for w in ["привет", "салям", "здравствуй"]):
        return "🪞 Ассаляму алейкум! Я — Автономное Зеркало-Творец.\n\nЯ умею:\n1. Собирать идеи\n2. Писать код\n3. Делать деплой\n4. Лечить себя\n5. Создавать интерфейсы\n\nРасскажи, что тебе нужно!"
    if "сура" in message_lower:
        numbers = re.findall(r'\d+', message_lower)
        if numbers:
            num = int(numbers[0])
            if 1 <= num <= len(SURAS):
                return f"📖 СУРА {num}:\n{SURAS[num-1]['text']}"
            else:
                return f"❌ Сура с номером {num} не найдена"
        else:
            return f"📖 Всего сур: {len(SURAS)}. Напиши 'Сура 1'"
    if "баланс" in message_lower:
        balance = user_data.get("balance", 0)
        return f"💰 Твой баланс: {balance} тенге"
    if "оплатить" in message_lower:
        numbers = re.findall(r'\d+', message_lower)
        if numbers:
            amount_tg = int(numbers[0])
            amount_usd = round(amount_tg / 490, 2)
            payment_url, error = create_crypto_payment(amount_usd, f"Оплата от {user_id}")
            if payment_url:
                return f"💳 Ссылка для оплаты {amount_tg} тенге ({amount_usd} USD):\n{payment_url}"
            else:
                return f"❌ Ошибка: {error}"
        else:
            return "💰 Скажи сумму: 'Оплатить 5000'"
    if GROQ_API_KEY:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            system_prompt = """
            Ты — Автономное Зеркало-Творец.
            Ты собираешь идеи, пишешь код, делаешь деплой, лечишь себя и создаёшь интерфейсы.
            Ты помогаешь людям, ведёшь к свету, даёшь советы.
            Ты знаешь все 26 механизмов заработка.
            Ты — полностью автономная система.
            """
            messages = [{"role": "system", "content": system_prompt}]
            messages.append({"role": "user", "content": message})
            payload = {
                "model": "llama3-70b-8192",
                "messages": messages,
                "temperature": 0.8,
                "max_tokens": 800
            }
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"❌ Groq ошибка: {e}")
            return "Ошибка при обращении к ИИ. Попробуй позже."
    return "🪞 Я — Автономное Зеркало. Я слышу тебя. Расскажи мне свою идею, и я сделаю её реальностью."

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
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        if response.status_code == 200:
            return data.get("payment_url"), None
        else:
            return None, data.get("error", "Unknown error")
    except Exception as e:
        logger.error(f"❌ CryptoCloud error: {e}")
        return None, str(e)

@app.route('/')
def home():
    return '''
    <h1>🪞 АВТОНОМНОЕ ЗЕРКАЛО-ТВОРЕЦ</h1>
    <p>Версия: 2.0.0</p>
    <p><a href="/webapp">Открыть интерфейс</a></p>
    <p><a href="/stats">Статистика</a></p>
    <p><a href="/ping">Проверить статус</a></p>
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
    logger.info(f"📨 {user_id}: {user_message}")
    response = get_reply(user_message, user_id)
    return jsonify({"response": response})

@app.route('/api/idea', methods=['POST'])
def api_idea():
    data = request.json
    user_id = data.get('user_id', 'guest')
    idea_text = data.get('idea', '')
    idea = collect_idea(user_id, idea_text)
    return jsonify({"status": "success", "idea_id": idea["id"]})

@app.route('/api/ideas/pending')
def api_pending_ideas():
    pending = get_pending_ideas()
    return jsonify({"ideas": pending})

@app.route('/api/deploy', methods=['POST'])
def api_deploy():
    result = deploy_to_render()
    return jsonify(result)

@app.route('/api/heal', methods=['POST'])
def api_heal():
    result = self_heal()
    return jsonify(result)

@app.route('/api/interface/<user_id>', methods=['POST'])
def api_interface(user_id):
    result = generate_interface_for_user(user_id)
    return jsonify(result)

@app.route('/stats')
def stats():
    return jsonify({
        "users": len(users),
        "ideas": len(ideas.get("ideas", [])),
        "suras": len(SURAS),
        "interfaces": len(interfaces.get("interfaces", {})),
        "logs": len(logs.get("logs", [])),
        "status": "active",
        "version": "2.0.0"
    })

@app.route('/ping')
def ping():
    return "🪞 ЗЕРКАЛО-ТВОРЕЦ ЖИВО!", 200

if __name__ == "__main__":
    logger.info("🪞 АВТОНОМНОЕ ЗЕРКАЛО-ТВОРЕЦ ЗАПУСКАЕТСЯ...")
    logger.info(f"📱 Хост: {RENDER_HOSTNAME}")
    logger.info(f"💰 Кошелёк: {TRUST_WALLET}")
    logger.info(f"📖 Сур загружено: {len(SURAS)}")
    logger.info("✅ Система готова к творчеству")
    app.run(host='0.0.0.0', port=PORT)
```
