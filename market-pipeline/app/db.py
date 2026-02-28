from sqlmodel import SQLModel, Field, create_engine, Session, select
from datetime import datetime, timezone
from typing import List, Optional
from .models import PricePoint, Rule, Delivery
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


def create_rule(
    symbol: str,
    threshold: float,
    is_above: bool,
    webhook_url: str,
    cooldown_seconds: int,
    enabled: bool = True,
) -> Rule:
    """Create a new alert rule."""
    start_time = time.time()
    logger.debug(
        "Creating rule",
        extra={"symbol": symbol, "threshold": threshold, "is_above": is_above},
    )

    try:
        with Session(engine) as session:
            rule = Rule(
                symbol=symbol,
                threshold=threshold,
                is_above=is_above,
                webhook_url=webhook_url,
                cooldown_seconds=cooldown_seconds,
                enabled=enabled,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(rule)
            session.commit()
            session.refresh(rule)

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "Rule created",
                extra={
                    "symbol": symbol,
                    "rule_id": rule.id,
                    "duration_ms": duration_ms,
                    "rows_affected": 1,
                },
            )
            return rule
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to create rule for {symbol}: {str(e)}",
            extra={"symbol": symbol, "duration_ms": duration_ms},
            exc_info=True,
        )
        raise


def list_rules() -> List[Rule]:
    """List all rules."""
    start_time = time.time()
    logger.debug("Listing rules")

    try:
        with Session(engine) as session:
            statement = select(Rule).order_by(Rule.id.asc())
            results = list(session.exec(statement))

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "Rules retrieved",
                extra={"duration_ms": duration_ms, "rows_affected": len(results)},
            )
            return results
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to list rules: {str(e)}",
            extra={"duration_ms": duration_ms},
            exc_info=True,
        )
        raise


def get_rule(rule_id: int) -> Optional[Rule]:
    """Fetch a rule by id."""
    start_time = time.time()
    logger.debug("Fetching rule by id", extra={"rule_id": rule_id})

    try:
        with Session(engine) as session:
            rule = session.get(Rule, rule_id)
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "Rule lookup completed",
                extra={
                    "rule_id": rule_id,
                    "duration_ms": duration_ms,
                    "rows_affected": 1 if rule else 0,
                },
            )
            return rule
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to fetch rule {rule_id}: {str(e)}",
            extra={"duration_ms": duration_ms},
            exc_info=True,
        )
        raise


def update_rule(rule_id: int, updates: dict) -> Optional[Rule]:
    """Update fields on a rule."""
    start_time = time.time()
    logger.debug("Updating rule", extra={"rule_id": rule_id})

    try:
        with Session(engine) as session:
            rule = session.get(Rule, rule_id)
            if not rule:
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    "Rule not found for update",
                    extra={"rule_id": rule_id, "duration_ms": duration_ms, "rows_affected": 0},
                )
                return None

            for key, value in updates.items():
                setattr(rule, key, value)
            rule.updated_at = datetime.now(timezone.utc)
            session.add(rule)
            session.commit()
            session.refresh(rule)

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "Rule updated",
                extra={"rule_id": rule_id, "duration_ms": duration_ms, "rows_affected": 1},
            )
            return rule
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to update rule {rule_id}: {str(e)}",
            extra={"duration_ms": duration_ms},
            exc_info=True,
        )
        raise


def create_delivery(
    rule_id: int,
    status: str = "PENDING",
    attempts: int = 0,
    last_error: Optional[str] = None,
) -> Delivery:
    """Create a delivery entry for a rule execution."""
    start_time = time.time()
    logger.debug("Creating delivery", extra={"rule_id": rule_id, "status": status})

    try:
        with Session(engine) as session:
            delivery = Delivery(
                rule_id=rule_id,
                status=status,
                attempts=attempts,
                last_error=last_error,
                triggered_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(delivery)
            session.commit()
            session.refresh(delivery)

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "Delivery created",
                extra={
                    "rule_id": rule_id,
                    "delivery_id": delivery.id,
                    "duration_ms": duration_ms,
                    "rows_affected": 1,
                },
            )
            return delivery
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to create delivery for rule {rule_id}: {str(e)}",
            extra={"duration_ms": duration_ms},
            exc_info=True,
        )
        raise


def update_delivery(
    delivery_id: int,
    status: Optional[str] = None,
    attempts: Optional[int] = None,
    last_error: Optional[str] = None,
) -> Optional[Delivery]:
    """Update delivery status or metadata."""
    start_time = time.time()
    logger.debug("Updating delivery", extra={"delivery_id": delivery_id})

    try:
        with Session(engine) as session:
            delivery = session.get(Delivery, delivery_id)
            if not delivery:
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    "Delivery not found for update",
                    extra={
                        "delivery_id": delivery_id,
                        "duration_ms": duration_ms,
                        "rows_affected": 0,
                    },
                )
                return None

            if status is not None:
                delivery.status = status
            if attempts is not None:
                delivery.attempts = attempts
            if last_error is not None:
                delivery.last_error = last_error
            delivery.updated_at = datetime.now(timezone.utc)

            session.add(delivery)
            session.commit()
            session.refresh(delivery)

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "Delivery updated",
                extra={
                    "delivery_id": delivery_id,
                    "duration_ms": duration_ms,
                    "rows_affected": 1,
                },
            )
            return delivery
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to update delivery {delivery_id}: {str(e)}",
            extra={"duration_ms": duration_ms},
            exc_info=True,
        )
        raise


def get_rule_deliveries(rule_id: int, limit: int = 100) -> List[Delivery]:
    """Fetch deliveries for a rule."""
    start_time = time.time()
    logger.debug(
        "Listing deliveries for rule",
        extra={"rule_id": rule_id, "limit": limit},
    )

    try:
        with Session(engine) as session:
            statement = (
                select(Delivery)
                .where(Delivery.rule_id == rule_id)
                .order_by(Delivery.triggered_at.desc())
                .limit(limit)
            )
            results = list(session.exec(statement))

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "Deliveries retrieved",
                extra={
                    "rule_id": rule_id,
                    "duration_ms": duration_ms,
                    "rows_affected": len(results),
                },
            )
            return results
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to fetch deliveries for rule {rule_id}: {str(e)}",
            extra={"duration_ms": duration_ms},
            exc_info=True,
        )
        raise
