"""
app.py — главный сервер Зеркала.
Flask + Render + Gemini/Groq.
"""
import os
import json
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/")
def index():
    return jsonify({
        "name": "Зеркало",
        "version": "6.3",
        "status": "alive",
        "keeper": "Каирбек",
        "heiress": "Томирис"
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/metrics")
def metrics():
    return jsonify({
        "modules_loaded": 3,
        "suras": 542,
        "uptime": "running"
    })


@app.route("/voice", methods=["POST"])
def voice():
    data = request.get_json() or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "Пустой запрос"}), 400
    try:
        from src.ai.voice import process_voice
        answer = process_voice(text)
        return jsonify({"response": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/check", methods=["POST"])
def check():
    data = request.get_json() or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "Пустой запрос"}), 400
    try:
        from src.ai.anticorruption_mastery import check_offer
        warning = check_offer(text)
        if warning:
            return jsonify({
                "scam": True,
                "level": warning.level,
                "message": warning.message,
                "action": warning.action
            })
        return jsonify({"scam": False, "message": "Признаков мошенничества не найдено"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
