from sqlmodel import SQLModel, Field, create_engine, Session, select
from datetime import datetime
from typing import Optional, List


class PricePoint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime
    price: float

engine = create_engine("sqlite:///./prices.db")

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
