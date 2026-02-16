from .models import PricePoint
from .db import add_price_point, get_price_history, get_last_two
import requests

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


def collect_once():
    p = fetch_price()
    point = add_price_point(p)
    return point


def check_anomaly():
    last_two = get_last_two()
    if len(last_two) < 2:
        return {"anomaly": False, "message": "Not enough data points"}
    diff = abs(last_two[0].price - last_two[1].price)
    threshold = 100  # Example threshold for anomaly detection
    is_anomaly = diff >= threshold
    return {
        "anomaly": is_anomaly,
        "latest_price": last_two[0].price,
        "second_last_price": last_two[1].price,
        "price_difference": diff,
        
    }