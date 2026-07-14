import os
import requests

API_KEY = os.environ.get("GIS_API_KEY", "")

def search_business(query, lat, lon, radius=5000):
    if not API_KEY:
        return {"error": "2GIS API key not set"}
    url = "https://catalog.api.2gis.com/3.0/items"
    params = {
        "q": query,
        "point": f"{lon},{lat}",
        "radius": radius,
        "key": API_KEY,
        "fields": "items.point,items.name,items.address,items.phones"
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except:
        return {"error": "2GIS request failed"}
