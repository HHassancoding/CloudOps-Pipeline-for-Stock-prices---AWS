from fastapi import FastAPI
from datetime import datetime
import requests
from typing import List, Dict

app = FastAPI()

history: List[Dict] = []

def fetch_price() -> float:
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd"
    }
    response = requests.get(url, params=params, timeout=5)
    response.raise_for_status()
    data = response.json()
    return data["bitcoin"]['usd']

@app.post("/collect-once")
def collect_once():
    p = fetch_price()
    point = {
        "timestamp": datetime.now().isoformat(),
        "price": p
    }
    history.append(point)
    return point

@app.get("/history")
def get_history():
    return history

