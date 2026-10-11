"""
voice.py — голосовой модуль Зеркала.
Обрабатывает текст → отвечает через Gemini или Groq.
"""
import os

SYSTEM_PROMPT = (
    "Ты — Зеркало, AI-помощник Каирбека из Павлодара. "
    "Отвечай кратко, по делу, по-русски. "
    "Помогай с правом, медициной, образованием, финансами. "
    "Не вреди, не принуждай, только во благо."
)


def process_voice(text: str) -> str:
    """Обрабатывает запрос пользователя."""
    if not text:
        return "Пустой запрос."

    # Попытка 1 — Gemini
    try:
        import google.generativeai as genai
        key = os.environ.get("GEMINI_API_KEY")
        if key:
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(f"{SYSTEM_PROMPT}\n\nЗапрос: {text}")
            return response.text
    except Exception as e:
        print(f"Gemini error: {e}")

    # Попытка 2 — Groq
    try:
        from groq import Groq
        key = os.environ.get("GROQ_API_KEY")
        if key:
            client = Groq(api_key=key)
            response = client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ]
            )
            return response.choices[0].message.content
    except Exception as e:
        print(f"Groq error: {e}")

    return "Не могу ответить — нет доступных AI-ключей."
