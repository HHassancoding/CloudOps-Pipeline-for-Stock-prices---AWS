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


def add_price_point(price: float, symbol: str):
    """Add a price point for a specific cryptocurrency symbol."""
    with Session(engine) as session:
        point = PricePoint(timestamp=datetime.utcnow(), price=price, symbol=symbol)
        session.add(point)
        session.commit()
        session.refresh(point)
        return point
    
def get_price_history(symbol: str, limit: int = 100) -> List[PricePoint]:
    """Get price history for a specific cryptocurrency symbol."""
    with Session(engine) as session:
        statement = (
            select(PricePoint)
            .where(PricePoint.symbol == symbol)
            .order_by(PricePoint.timestamp.desc())
            .limit(limit)
        )
        return list(session.exec(statement))
    
def get_last_two(symbol: str) -> List[PricePoint]:
    """Get the last two price points for a specific cryptocurrency symbol."""
    with Session(engine) as session:
        statement = (
            select(PricePoint)
            .where(PricePoint.symbol == symbol)
            .order_by(PricePoint.timestamp.desc())
            .limit(2)
        )
        return list(session.exec(statement))
