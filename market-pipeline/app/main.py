from fastapi import FastAPI, HTTPException, Request
from contextlib import asynccontextmanager
from typing import List
import requests
import time
import uuid
import logging

from .db import init_db, get_price_history
from .models import PricePoint, SYMBOL_TO_ID
from .services import collect_once, check_anomaly
from .logging_config import get_logger, set_trace_id, clear_trace_id
from . import add_trace_id_middleware

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting CloudOps Market Data Pipeline")
    try:
        init_db()
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}", exc_info=True)
        raise
    yield


app = FastAPI(title="Market Data Pipeline", lifespan=lifespan)

# Register middleware for trace ID injection
app.middleware("http")(add_trace_id_middleware)


@app.post("/collect-once/{symbol}", response_model=PricePoint)
def collect_once_endpoint(symbol: str, request: Request):
    """Collect a single price point for the given cryptocurrency symbol.
    
    Args:
        symbol: Cryptocurrency symbol (BTC, ETH, SOL, ADA, DOT)
        
    Returns:
        PricePoint: The collected price data
        
    Raises:
        HTTPException 400: If symbol is not supported
        HTTPException 503: If external API call fails
    """
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    start_time = time.time()
    
    logger.info(
        "POST /collect-once request received",
        extra={"symbol": symbol}
    )
    
    try:
        client_ip = request.client.host if request.client else None
        result = collect_once(symbol, client_ip=client_ip)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"POST /collect-once completed successfully for {symbol}",
            extra={"symbol": symbol, "duration_ms": duration_ms, "status_code": 200}
        )
        clear_trace_id()
        return result
    except ValueError as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Invalid symbol: {symbol}",
            extra={"symbol": symbol, "duration_ms": duration_ms, "status_code": 400}
        )
        clear_trace_id()
        raise HTTPException(status_code=400, detail=str(e))
    except requests.RequestException as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"External API error for {symbol}: {str(e)}",
            extra={"symbol": symbol, "duration_ms": duration_ms, "status_code": 503}
        )
        clear_trace_id()
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
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    start_time = time.time()
    
    logger.debug(
        f"GET /history request received for {symbol} with limit={limit}",
        extra={"symbol": symbol}
    )
    
    normalized_symbol = symbol.upper()
    if normalized_symbol not in SYMBOL_TO_ID:
        supported = ", ".join(SYMBOL_TO_ID.keys())
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Invalid symbol in history request: {symbol}",
            extra={"symbol": symbol, "duration_ms": duration_ms, "status_code": 400}
        )
        clear_trace_id()
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported symbol: {symbol}. Supported symbols: {supported}"
        )
    
    result = get_price_history(normalized_symbol, limit)
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        f"GET /history completed for {normalized_symbol}, returned {len(result)} records",
        extra={"symbol": normalized_symbol, "duration_ms": duration_ms, "rows_affected": len(result), "status_code": 200}
    )
    clear_trace_id()
    return result


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
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    start_time = time.time()
    
    logger.debug(
        f"GET /anomaly request received for {symbol}",
        extra={"symbol": symbol}
    )
    
    try:
        result = check_anomaly(symbol)
        duration_ms = (time.time() - start_time) * 1000
        anomaly_detected = result.get("anomaly", False)
        log_level = logging.WARNING if anomaly_detected else logging.INFO
        logger.log(
            log_level,
            f"Anomaly check completed for {symbol}, anomaly_detected={anomaly_detected}",
            extra={"symbol": symbol, "duration_ms": duration_ms, "status_code": 200}
        )
        clear_trace_id()
        return result
    except ValueError as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Invalid symbol in anomaly request: {symbol}",
            extra={"symbol": symbol, "duration_ms": duration_ms, "status_code": 400}
        )
        clear_trace_id()
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/supported-symbols")
def supported_symbols_endpoint():
    """List all supported cryptocurrency symbols.
    
    Returns:
        dict: Dictionary containing list of supported symbols and their CoinGecko IDs
    """
    logger.debug("GET /supported-symbols request received")
    return {
        "symbols": list(SYMBOL_TO_ID.keys()),
        "mappings": SYMBOL_TO_ID
    }
