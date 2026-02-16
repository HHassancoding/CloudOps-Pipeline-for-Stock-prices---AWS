from fastapi import FastAPI
from typing import List

from .db import init_db, get_price_history
from .models import PricePoint
from .services import collect_once, check_anomaly

app = FastAPI(title="Market Data Pipeline")


@app.on_event("startup")
def on_startup():
    init_db()


@app.post("/collect-once", response_model=PricePoint)
def collect_once_endpoint():
    return collect_once()


@app.get("/history", response_model=List[PricePoint])
def history_endpoint(limit: int = 100):
    return get_price_history(limit)


@app.get("/anomaly")
def anomaly_endpoint():
    return check_anomaly()
