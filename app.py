#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
import logging
import requests
import time
import hashlib
import base64
from datetime import datetime
from flask import Flask, send_from_directory, request, jsonify

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

def load_json(filename, default=None):
    if default is None:
        default = {}
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
        logger.info(f"Loaded {len(suras)} suras")
        return suras
    except Exception as e:
        logger.error(f"Error loading suras: {e}")
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
    logger.info(f"New idea from {user_id}: {idea_text[:50]}...")
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
        return {"error": "Idea not found"}
    update_idea(idea_id, {
        "discussed_with_founder": True,
        "founder_decision": founder_decision,
        "founder_comment": founder_comment,
        "discussed_at": datetime.now().isoformat()
    })
    if founder_decision == "implement":
        generate_code_from_idea(idea_id)
        return {"status": "implementing", "message": "Generating code..."}
    elif founder_decision == "reject":
        return {"status": "rejected", "message": "Idea rejected"}
    else:
        return {"status": "pending", "message": "Needs more discussion"}

def generate_code_from_idea(idea_id):
    idea = get_idea_by_id(idea_id)
    if not idea:
        return {"error": "Idea not found"}
    if not GROQ_API_KEY:
        return {"error": "GROQ_API_KEY not set"}
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        relevant_suras = "\n".join([s["text"][:300] for s in SURAS[:5]])
        prompt = f"""
        You are an autonomous Mirror-Creator. Write Python code.
        User idea: {idea['text']}
        Context from suras: {relevant_suras}
        Write working, safe, integrated Python code.
        Only code, no explanations.
        Format:
        ```python
        # code here
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
        logger.info(f"Code generated for idea {idea_id}")
        return {"status": "code_generated", "file": module_name}
    except Exception as e:
        logger.error(f"Code generation error: {e}")
        return {"error": str(e)}

def push_to_github(file_path, commit_message):
    if not GITHUB_TOKEN:
        return {"error": "GITHUB_TOKEN not set"}
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
            logger.info(f"File {path} updated in GitHub")
            return {"status": "success"}
        else:
            logger.error(f"GitHub error: {response.text}")
            return {"error": response.text}
    except Exception as e:
        logger.error(f"GitHub push error: {e}")
        return {"error": str(e)}

def deploy_to_render():
    if not RENDER_API_KEY:
        return {"error": "RENDER_API_KEY not set"}
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
            logger.info("Deploy started on Render")
            return {"status": "deploy_started", "message": "Deploy started"}
        else:
            logger.error(f"Render deploy error: {response.text}")
            return {"error": response.text}
    except Exception as e:
        logger.error(f"Render deploy error: {e}")
        return {"error": str(e)}

def self_heal():
    logger.info("Running self-diagnostic...")
    issues = []
    if not GROQ_API_KEY:
        issues.append("GROQ_API_KEY not set")
    if not CRYPTO_CLOUD_API_KEY:
        issues.append("CRYPTO_CLOUD_API_KEY not set")
    if not GITHUB_TOKEN:
        issues.append("GITHUB_TOKEN not set")
    if not RENDER_API_KEY:
        issues.append("RENDER_API_KEY not set")
    try:
        requests.get("https://api.groq.com/openai/v1/models", timeout=5)
    except:
        issues.append("Groq API unavailable")
    try:
        requests.get("https://api.trybit.com/v1/ping", timeout=5)
    except:
        issues.append("CryptoCloud API unavailable")
    if len(SURAS) < 100:
        issues.append("Low sura count, possible file corruption")
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
        logger.warning(f"Issues found: {issues}")
        return {"status": "issues_found", "issues": issues}
    else:
        logger.info("System healthy")
        return {"status": "healthy", "message": "All systems working"}

def generate_interface_for_user(user_id):
    style = {
        "background": "#0a0a0a",
        "text_color": "#ffffff",
        "accent": "#00d4ff",
        "font": "Arial"
    }
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zerkalo</title>
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
            <h1>Zerkalo</h1>
            <p>Your personal assistant</p>
        </div>
        <div class="chat-box" id="chat-box">
            <div class="message zerkalo">Assalamu alaykum! I am Mirror. How can I help you today?</div>
        </div>
        <div class="input-area">
            <input type="text" id="message-input" placeholder="Write a message..." />
            <button id="send-btn">Send</button>
            <button class="voice-btn" id="voice-btn">Voice</button>
        </div>
        <div class="footer">
            <span>Zerkalo v2.0</span>
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
                addMessage('Connection error', 'zerkalo');
            }}
        }}
        sendBtn.addEventListener('click', sendMessage);
        input.addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') sendMessage();
        }});
        if ('webkitSpeechRecognition' in window) {{
            const recognition = new webkitSpeechRecognition();
            recognition.lang = 'en-US';
            recognition.continuous = false;
            recognition.interimResults = false;
            voiceBtn.addEventListener('click', () => {{
                recognition.start();
                voiceBtn.textContent = 'Listening...';
            }});
            recognition.onresult = (event) => {{
                const text = event.results[0][0].transcript;
                input.value = text;
                sendMessage();
                voiceBtn.textContent = 'Voice';
            }};
            recognition.onerror = () => {{
                voiceBtn.textContent = 'Voice';
                addMessage('Voice recognition failed', 'zerkalo');
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
    logger.info(f"Interface created for {user_id}")
    return {"status": "created", "file": filename}

def create_crypto_payment(amount_usd, description="Payment via Mirror"):
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
        logger.error(f"CryptoCloud error: {e}")
        return None, str(e)

def get_reply(message, user_id="guest"):
    message_lower = message.lower().strip()
    user_data = users.get(user_id, {})
    if any(w in message_lower for w in ["idea", "proposal", "i want to", "i have an idea"]):
        for keyword in ["idea", "proposal", "i want to", "i have an idea"]:
            if keyword in message_lower:
                idea_text = message[message_lower.find(keyword) + len(keyword):].strip()
                if len(idea_text) < 10:
                    return "Tell me more about your idea. What do you want to create?"
                break
        else:
            idea_text = message
        idea = collect_idea(user_id, idea_text)
        return f"""
Idea received!
I saved your idea: {idea_text}
Status: Waiting for Founder's review.
When Founder approves, I will write code and deploy it.
Thank you for contributing to Mirror! 🪞
"""
    if user_id in ADMIN_IDS:
        if "new ideas" in message_lower or "ideas" in message_lower:
            pending = get_pending_ideas()
            if not pending:
                return "No new ideas. All ideas are being discussed."
            result = "NEW IDEAS:\n\n"
            for i in pending[-5:]:
                result += f"ID: {i['id']}\n"
                result += f"From: {i['user_id']}\n"
                result += f"Idea: {i['text'][:200]}...\n"
                result += f"Status: {i.get('status', 'new')}\n"
                result += "-" * 30 + "\n"
            result += "\nTo discuss an idea, write: 'Discuss idea [ID]'"
            return result
        if "discuss idea" in message_lower:
            match = re.search(r'idea\s+(\S+)', message_lower)
            if match:
                idea_id = match.group(1)
                idea = get_idea_by_id(idea_id)
                if not idea:
                    return f"Idea with ID {idea_id} not found"
                return f"""
IDEA DISCUSSION
ID: {idea['id']}
From: {idea['user_id']}
Idea: {idea['text']}
Status: {idea.get('status', 'new')}
What do you want to do?
1. 'Approve idea' - start code generation
2. 'Reject idea' - close it
3. 'Discuss' - add comment
"""
        if "approve idea" in message_lower:
            match = re.search(r'idea\s+(\S+)', message_lower)
            if match:
                idea_id = match.group(1)
                result = discuss_idea_with_founder(idea_id, "implement")
                return f"✅ {result.get('message', 'Idea approved')}"
        if "reject idea" in message_lower:
            match = re.search(r'idea\s+(\S+)', message_lower)
            if match:
                idea_id = match.group(1)
                result = discuss_idea_with_founder(idea_id, "reject")
                return f"❌ {result.get('message', 'Idea rejected')}"
        if "deploy" in message_lower:
            result = deploy_to_render()
            return f"🚀 {result.get('message', 'Deploy started')}"
        if "diagnostic" in message_lower or "health" in message_lower:
            result = self_heal()
            if result["status"] == "healthy":
                return "✅ All systems working perfectly!"
            else:
                return f"⚠️ Issues found:\n" + "\n".join(result.get("issues", []))
        if "create interface" in message_lower:
            match = re.search(r'for\s+(\S+)', message_lower)
            if match:
                target_user = match.group(1)
                result = generate_interface_for_user(target_user)
                return f"Interface created for {target_user}\nAvailable at: /webapp/index_{target_user}.html"
        if "status" in message_lower:
            return f"""
MIRROR STATUS
Users: {len(users)}
Ideas: {len(ideas.get('ideas', []))}
Suras loaded: {len(SURAS)}
Interfaces: {len(interfaces.get('interfaces', {}))}
Logs: {len(logs.get('logs', []))}
Balance: {users.get(FOUNDER_ID, {}).get('balance', 0)} KZT
System is autonomous and ready
"""
    if "new interface" in message_lower or "different design" in message_lower:
        result = generate_interface_for_user(user_id)
        return f"""
NEW INTERFACE CREATED!
Your personal interface is available at:
/webapp/index_{user_id}.html
You can customize it by telling me what to change.
"""
    if any(w in message_lower for w in ["hello", "salam", "hi", "greetings"]):
        return "Assalamu alaykum! I am Autonomous Mirror-Creator.\n\nI can:\n1. Collect ideas\n2. Write code\n3. Deploy\n4. Heal myself\n5. Create interfaces\n\nTell me what you need!"
    if "sura" in message_lower:
        numbers = re.findall(r'\d+', message_lower)
        if numbers:
            num = int(numbers[0])
            if 1 <= num <= len(SURAS):
                return f"SURA {num}:\n{SURAS[num-1]['text']}"
            else:
                return f"Sura {num} not found"
        else:
            return f"Total suras: {len(SURAS)}. Write 'Sura 1'"
    if "balance" in message_lower:
        balance = user_data.get("balance", 0)
        return f"Your balance: {balance} KZT"
    if "pay" in message_lower:
        numbers = re.findall(r'\d+', message_lower)
        if numbers:
            amount_tg = int(numbers[0])
            amount_usd = round(amount_tg / 490, 2)
            payment_url, error = create_crypto_payment(amount_usd, f"Payment from {user_id}")
            if payment_url:
                return f"Payment link for {amount_tg} KZT ({amount_usd} USD):\n{payment_url}"
            else:
                return f"Error: {error}"
        else:
            return "Tell me the amount: 'Pay 5000'"
    if GROQ_API_KEY:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            system_prompt = """
            You are Autonomous Mirror-Creator.
            You collect ideas, write code, deploy, heal yourself, create interfaces.
            You help people, guide to light, give advice.
            You know all 26 earning mechanisms.
            You are a fully autonomous system.
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
            logger.error(f"Groq error: {e}")
            return "Error contacting AI. Try again later."
    return "I am Autonomous Mirror. I hear you. Tell me your idea, and I will make it real."

@app.route('/')
def home():
    return '''
    <h1>Autonomous Mirror-Creator</h1>
    <p>Version: 2.0.0</p>
    <p><a href="/webapp">Open interface</a></p>
    <p><a href="/stats">Statistics</a></p>
    <p><a href="/ping">Check status</a></p>
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
    logger.info(f"Message from {user_id}: {user_message}")
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
    return "Mirror-Creator is alive!", 200

if __name__ == "__main__":
    logger.info("Starting Autonomous Mirror-Creator...")
    logger.info(f"Host: {RENDER_HOSTNAME}")
    logger.info(f"Wallet: {TRUST_WALLET}")
    logger.info(f"Suras loaded: {len(SURAS)}")
    logger.info("System ready for creation")
    app.run(host='0.0.0.0', port=PORT)
