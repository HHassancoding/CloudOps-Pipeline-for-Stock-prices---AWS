from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from typing import Optional, List, Dict
from app.logging_config import get_logger

logger = get_logger(__name__)

# Symbol to CoinGecko ID mapping
SYMBOL_TO_ID: Dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "ADA": "cardano",
    "DOT": "polkadot",
}

DELIVERY_STATUSES: List[str] = ["PENDING", "SENT", "FAILED"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_symbol(symbol: str) -> str:
    """Validate and normalize cryptocurrency symbol.
    
    Args:
        symbol: Raw symbol string (case-insensitive)
        
    Returns:
        Normalized uppercase symbol
        
    Raises:
        ValueError: If symbol is not supported
    """
    normalized = symbol.upper()
    if normalized not in SYMBOL_TO_ID:
        supported = ", ".join(SYMBOL_TO_ID.keys())
        logger.error(
            f"Symbol validation failed: {symbol}",
            extra={"symbol": symbol}
        )
        raise ValueError(f"Unsupported symbol: {symbol}. Supported symbols: {supported}")
    
    logger.debug(f"Symbol validated successfully: {normalized}", extra={"symbol": normalized})
    return normalized


class PricePoint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime
    price: float
    symbol: str = Field(index=True)  # "BTC", "ETH", etc.


class Rule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    threshold: float
    is_above: bool
    webhook_url: str
    cooldown_seconds: int
    enabled: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class Delivery(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    rule_id: int = Field(foreign_key="rule.id", index=True)
    triggered_at: datetime = Field(default_factory=_utc_now, index=True)
    status: str = Field(default="PENDING", index=True)
    attempts: int = Field(default=0)
    last_error: Optional[str] = Field(default=None)
    updated_at: datetime = Field(default_factory=_utc_now)