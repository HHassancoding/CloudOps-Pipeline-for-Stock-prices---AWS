from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional, List, Dict


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
        raise ValueError(f"Unsupported symbol: {symbol}. Supported symbols: {supported}")
    return normalized


class PricePoint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime
    price: float
    symbol: str = Field(index=True)  # "BTC", "ETH", etc.