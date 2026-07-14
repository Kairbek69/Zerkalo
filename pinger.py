import requests
import time
import os

def ping_self():
    url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'zerkalo-6sla.onrender.com')}/ping"
    while True:
        try:
            requests.get(url, timeout=10)
        except:
            pass
        time.sleep(60)

if __name__ == "__main__":
    ping_self()
