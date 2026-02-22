from sqlmodel import SQLModel, Field
from datetime import datetime
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