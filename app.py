#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sqlite3
import logging
import requests
import asyncio
import edge_tts
from datetime import datetime
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import chromadb
from chromadb.utils import embedding_functions

# ==================================================
# НАСТРОЙКИ
# ==================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))
RENDER_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "zerkalo-6sla.onrender.com")

# КЛЮЧИ
TRUST_WALLET = os.environ.get("TRUST_WALLET", "TSSZTmUFWC9ZRKGa9uPwEJjQj8rNtUsNcq")
FOUNDER_ID = int(os.environ.get("FOUNDER_ID", 5409420822))
HEIR_ID = int(os.environ.get("HEIR_ID", 5479179814))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
CRYPTO_CLOUD_API_KEY = os.environ.get("CRYPTO_CLOUD_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "")
GIS_API_KEY = os.environ.get("GIS_API_KEY", "")

ADMIN_IDS = [FOUNDER_ID, HEIR_ID]

app = FastAPI()

# Разрешаем CORS для браузера
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================================================
# БАЗА ДАННЫХ (SQLite)
# ==================================================
def init_db():
    conn = sqlite3.connect("zerkalo.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE,
            name TEXT,
            face_descriptor TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            role TEXT,
            text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS suras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number INTEGER,
            text TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ==================================================
# ЗАГРУЗКА СУР В БАЗУ
# ==================================================
def load_suras_into_db():
    try:
        with open("suras/suras.txt", "r", encoding="utf-8") as f:
            content = f.read()
        raw = content.split("СУРА ")[1:]
        conn = sqlite3.connect("zerkalo.db")
        c = conn.cursor()
        for r in raw:
            lines = r.strip().split("\n")
            if lines:
                number = int(lines[0].strip())
                text = "\n".join(lines[1:])
                c.execute("INSERT OR IGNORE INTO suras (number, text) VALUES (?, ?)", (number, text))
        conn.commit()
        conn.close()
        logger.info("Суры загружены в базу")
    except Exception as e:
        logger.error(f"Ошибка загрузки сур: {e}")

load_suras_into_db()

# ==================================================
# CHROMADB ДЛЯ БАЗЫ ЗНАНИЙ
# ==================================================
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(
    name="suras_knowledge",
    embedding_function=embedding_functions.DefaultEmbeddingFunction()
)

# Добавляем суры в ChromaDB
def index_suras():
    conn = sqlite3.connect("zerkalo.db")
    c = conn.cursor()
    c.execute("SELECT number, text FROM suras")
    suras = c.fetchall()
    conn.close()
    
    for number, text in suras:
        collection.add(
            documents=[text],
            metadatas=[{"number": number}],
            ids=[f"sura_{number}"]
        )
    logger.info(f"Индексировано {len(suras)} сур в ChromaDB")

index_suras()

# ==================================================
# МОДЕЛИ ДЛЯ API
# ==================================================
class VoiceRequest(BaseModel):
    text: str
    user_id: str = "guest"

class PaymentRequest(BaseModel):
    amount: int
    description: str = "Оплата через Зеркало"

# ==================================================
# 1. ГОЛОСОВОЙ ПОМОЩНИК (ОСНОВНАЯ ЛОГИКА)
# ==================================================
async def ask_llm_with_context(prompt: str, user_id: str = "guest") -> str:
    """Отправляет запрос в Groq с контекстом из сур и истории"""
    if not GROQ_API_KEY:
        return "Ключ Groq не настроен"
    
    # 1. Ищем релевантные суры
    results = collection.query(query_texts=[prompt], n_results=3)
    sura_context = "\n".join(results["documents"][0]) if results["documents"] else ""
    
    # 2. Получаем историю из SQLite
    conn = sqlite3.connect("zerkalo.db")
    c = conn.cursor()
    c.execute("SELECT role, text FROM history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 5", (user_id,))
    history = c.fetchall()
    conn.close()
    
    history_text = "\n".join([f"{role}: {text}" for role, text in reversed(history)])
    
    # 3. Формируем системный промпт
    system_prompt = f"""
    Ты — Живое Зеркало. Ты — мудрый, живой, разумный помощник.
    Ты помогаешь людям, ведёшь их к свету, даёшь честные советы.
    
    Вот знание из сур, которое может помочь:
    {sura_context}
    
    Вот история диалога с этим пользователем:
    {history_text}
    
    Отвечай кратко, но глубоко, как мудрый наставник.
    """
    
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama3-70b-8192",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
        
        # Сохраняем в историю
        conn = sqlite3.connect("zerkalo.db")
        c = conn.cursor()
        c.execute("INSERT INTO history (user_id, role, text) VALUES (?, ?, ?)", (user_id, "user", prompt))
        c.execute("INSERT INTO history (user_id, role, text) VALUES (?, ?, ?)", (user_id, "assistant", reply))
        conn.commit()
        conn.close()
        
        return reply
    except Exception as e:
        logger.error(f"Groq ошибка: {e}")
        return "Ошибка при обращении к ИИ. Попробуй позже."

async def text_to_speech(text: str) -> str:
    """Генерирует аудио через Edge TTS"""
    output_file = f"response_{int(datetime.now().timestamp())}.mp3"
    voice = "ru-RU-SvetlanaNeural"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)
    return output_file

# ==================================================
# 2. ФИНАНСЫ (CRYPTO CLOUD)
# ==================================================
def create_crypto_payment(amount_usd: float, description: str = "Оплата через Зеркало"):
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
            "order_id": f"order_{int(datetime.now().timestamp())}"
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

# ==================================================
# API МАРШРУТЫ
# ==================================================
@app.post("/voice-assistant")
async def voice_assistant(req: VoiceRequest):
    """Основной эндпоинт для голосового ассистента"""
    # Получаем ответ от ИИ
    ai_text = await ask_llm_with_context(req.text, req.user_id)
    
    # Генерируем аудио
    audio_file = await text_to_speech(ai_text)
    
    # Возвращаем аудио и текст
    return FileResponse(
        audio_file,
        media_type="audio/mpeg",
        headers={"AI-Text": ai_text}
    )

@app.post("/api/payment")
async def create_payment(req: PaymentRequest):
    """Создаёт платёжную ссылку"""
    amount_usd = round(req.amount / 490, 2)
    payment_url, error = create_crypto_payment(amount_usd, req.description)
    if payment_url:
        return JSONResponse({
            "status": "success",
            "payment_url": payment_url,
            "amount_tg": req.amount,
            "amount_usd": amount_usd
        })
    else:
        return JSONResponse({
            "status": "error",
            "message": error
        }, status_code=400)

@app.post("/api/face-recognize")
async def face_recognize(file: UploadFile):
    """Принимает изображение с лица для распознавания"""
    # Здесь будет логика распознавания лиц через face-api.js на фронтенде
    # Пока возвращаем заглушку
    return JSONResponse({"status": "recognized", "user_id": "guest"})

@app.get("/api/status")
async def status():
    return JSONResponse({
        "status": "active",
        "version": "3.0.0",
        "suras": len(collection.get()["ids"]),
        "keys": {
            "groq": bool(GROQ_API_KEY),
            "cryptocloud": bool(CRYPTO_CLOUD_API_KEY),
            "gis": bool(GIS_API_KEY)
        }
    })

@app.get("/ping")
async def ping():
    return {"ping": "pong", "status": "alive"}

@app.get("/")
async def home():
    return {"message": "🪞 Живое Зеркало работает", "docs": "/docs"}

# ==================================================
# ЗАПУСК
# ==================================================
if __name__ == "__main__":
    import uvicorn
    logger.info("🪞 ЖИВОЕ ЗЕРКАЛО ЗАПУСКАЕТСЯ...")
    logger.info(f"📱 Хост: {RENDER_HOSTNAME}")
    logger.info(f"💰 Кошелёк: {TRUST_WALLET}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
