import datetime
import json

reminders = {}  # user_id -> {"time": "2026-07-15 14:00", "text": "Встреча"}

def set_reminder(user_id, text, time_str):
    reminders[user_id] = {"text": text, "time": time_str}
    return f"✅ Напоминание установлено на {time_str}: {text}"

def check_reminders():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    for user_id, data in reminders.items():
        if data["time"] == now:
            return f"🔔 Напоминание для {user_id}: {data['text']}"
    return None
