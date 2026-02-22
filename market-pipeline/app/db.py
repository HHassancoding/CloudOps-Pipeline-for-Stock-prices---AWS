from sqlmodel import SQLModel, Field, create_engine, Session, select
from datetime import datetime, timezone
from typing import List
from .models import PricePoint
import os
from dotenv import load_dotenv
import time
import logging
from .logging_config import get_logger

logger = get_logger(__name__)

load_dotenv()  # Load environment variables from .env file

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./prices.db")
logger.info(f"Database connection string: {DATABASE_URL.split('@')[0] if '@' in DATABASE_URL else DATABASE_URL.split('/')[-1]}")
engine = create_engine(DATABASE_URL)

def init_db():
    logger.info("Initializing database and creating tables")
    try:
        SQLModel.metadata.create_all(engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}", exc_info=True)
        raise


def add_price_point(price: float, symbol: str):
    """Add a price point for a specific cryptocurrency symbol."""
    start_time = time.time()
    logger.debug(f"Inserting price point for {symbol}: ${price}", extra={"symbol": symbol})
    
    try:
        with Session(engine) as session:
            point = PricePoint(timestamp=datetime.now(timezone.utc), price=price, symbol=symbol)
            session.add(point)
            session.commit()
            session.refresh(point)
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Price point inserted for {symbol} (ID: {point.id})",
                extra={"symbol": symbol, "duration_ms": duration_ms, "rows_affected": 1}
            )
            return point
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to insert price point for {symbol}: {str(e)}",
            extra={"symbol": symbol, "duration_ms": duration_ms},
            exc_info=True
        )
        raise
    
def get_price_history(symbol: str, limit: int = 100) -> List[PricePoint]:
    """Get price history for a specific cryptocurrency symbol."""
    start_time = time.time()
    logger.debug(f"Querying price history for {symbol} with limit={limit}", extra={"symbol": symbol})
    
    try:
        with Session(engine) as session:
            statement = (
                select(PricePoint)
                .where(PricePoint.symbol == symbol)
                .order_by(PricePoint.timestamp.desc())
                .limit(limit)
            )
            results = list(session.exec(statement))
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Price history retrieved for {symbol}: {len(results)} records",
                extra={"symbol": symbol, "duration_ms": duration_ms, "rows_affected": len(results)}
            )
            return results
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to retrieve price history for {symbol}: {str(e)}",
            extra={"symbol": symbol, "duration_ms": duration_ms},
            exc_info=True
        )
        raise
    
def get_last_two(symbol: str) -> List[PricePoint]:
    """Get the last two price points for a specific cryptocurrency symbol."""
    start_time = time.time()
    logger.debug(f"Querying last two price points for {symbol}", extra={"symbol": symbol})
    
    try:
        with Session(engine) as session:
            statement = (
                select(PricePoint)
                .where(PricePoint.symbol == symbol)
                .order_by(PricePoint.timestamp.desc())
                .limit(2)
            )
            results = list(session.exec(statement))
            
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(
                f"Last two price points retrieved for {symbol}: {len(results)} records",
                extra={"symbol": symbol, "duration_ms": duration_ms, "rows_affected": len(results)}
            )
            return results
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to retrieve last two price points for {symbol}: {str(e)}",
            extra={"symbol": symbol, "duration_ms": duration_ms},
            exc_info=True
        )
        raise
