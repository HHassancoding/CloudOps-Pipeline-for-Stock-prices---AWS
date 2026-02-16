from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional, List


class PricePoint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime
    price: float