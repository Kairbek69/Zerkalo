import os
import requests

TRUST_WALLET = os.environ.get("TRUST_WALLET", "TSSZTmUFWC9ZRKGa9uPwEJjQj8rNtUsNcq")

def generate_qr(amount, description="Оплата через Зеркало"):
    return f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=Оплата%20{amount}%20тг%20{description}"

def check_balance():
    try:
        url = f"https://api.trongrid.io/v1/accounts/{TRUST_WALLET}"
        r = requests.get(url, timeout=10)
        data = r.json()
        return data.get("balance", 0) / 1_000_000
    except:
        return 0
