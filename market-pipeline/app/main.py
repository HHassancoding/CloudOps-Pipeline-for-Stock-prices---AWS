from fastapi import FastAPI, HTTPException
from typing import List
import requests

from .db import init_db, get_price_history
from .models import PricePoint, SYMBOL_TO_ID
from .services import collect_once, check_anomaly

app = FastAPI(title="Market Data Pipeline")


@app.on_event("startup")
def on_startup():
    init_db()


@app.post("/collect-once/{symbol}", response_model=PricePoint)
def collect_once_endpoint(symbol: str):
    """Collect a single price point for the given cryptocurrency symbol.
    
    Args:
        symbol: Cryptocurrency symbol (BTC, ETH, SOL, ADA, DOT)
        
    Returns:
        PricePoint: The collected price data
        
    Raises:
        HTTPException 400: If symbol is not supported
        HTTPException 503: If external API call fails
    """
    try:
        return collect_once(symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"External API error: {str(e)}")


@app.get("/history/{symbol}", response_model=List[PricePoint])
def history_endpoint(symbol: str, limit: int = 100):
    """Get price history for the given cryptocurrency symbol.
    
    Args:
        symbol: Cryptocurrency symbol (BTC, ETH, SOL, ADA, DOT)
        limit: Maximum number of records to return (default: 100)
        
    Returns:
        List[PricePoint]: Historical price data in descending order by timestamp
        
    Raises:
        HTTPException 400: If symbol is not supported
    """
    normalized_symbol = symbol.upper()
    if normalized_symbol not in SYMBOL_TO_ID:
        supported = ", ".join(SYMBOL_TO_ID.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported symbol: {symbol}. Supported symbols: {supported}"
        )
    return get_price_history(normalized_symbol, limit)


@app.get("/anomaly/{symbol}")
def anomaly_endpoint(symbol: str):
    """Check for price anomalies for the given cryptocurrency symbol.
    
    Args:
        symbol: Cryptocurrency symbol (BTC, ETH, SOL, ADA, DOT)
        
    Returns:
        dict: Anomaly detection result including latest prices and difference
        
    Raises:
        HTTPException 400: If symbol is not supported
    """
    try:
        return check_anomaly(symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/supported-symbols")
def supported_symbols_endpoint():
    """List all supported cryptocurrency symbols.
    
    Returns:
        dict: Dictionary containing list of supported symbols and their CoinGecko IDs
    """
    return {
        "symbols": list(SYMBOL_TO_ID.keys()),
        "mappings": SYMBOL_TO_ID
    }
