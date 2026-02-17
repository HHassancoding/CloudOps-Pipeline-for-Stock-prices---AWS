from sqlmodel import SQLModel, Field, create_engine, Session, select
from datetime import datetime
from typing import List
from .models import PricePoint
import os
from dotenv import load_dotenv  

load_dotenv()  # Load environment variables from .env file

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./prices.db")
engine = create_engine(DATABASE_URL)

def init_db():
    SQLModel.metadata.create_all(engine)


def add_price_point(price: float):
    with Session(engine) as session:
        point = PricePoint(timestamp=datetime.utcnow(), price=price)
        session.add(point)
        session.commit()
        session.refresh(point)
        return point
    
def get_price_history(limit: int =100) -> List[PricePoint]:
    with Session(engine) as session:
        statement = select(PricePoint).order_by(PricePoint.timestamp.desc()).limit(limit)
        return list(session.exec(statement))
    
def get_last_two() -> List[PricePoint]:
    with Session(engine) as session:
        statement = select(PricePoint).order_by(PricePoint.timestamp.desc()).limit(2)
        return list(session.exec(statement))
