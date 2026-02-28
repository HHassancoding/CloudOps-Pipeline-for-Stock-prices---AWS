from fastapi import FastAPI, HTTPException, Request
from contextlib import asynccontextmanager
from typing import List, Optional
import requests
import time
import uuid
import logging
from pydantic import BaseModel

from .db import init_db, get_price_history
from .models import PricePoint, SYMBOL_TO_ID, Rule, Delivery
from .services import (
    collect_once,
    check_anomaly,
    create_rule_service,
    list_rules_service,
    update_rule_service,
    list_rule_deliveries_service,
)
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


class RuleCreate(BaseModel):
    symbol: str
    threshold: float
    is_above: bool
    webhook_url: str
    cooldown_seconds: int
    enabled: bool = True


class RuleUpdate(BaseModel):
    threshold: Optional[float] = None
    is_above: Optional[bool] = None
    webhook_url: Optional[str] = None
    cooldown_seconds: Optional[int] = None
    enabled: Optional[bool] = None


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


@app.post("/rules", response_model=Rule)
def create_rule_endpoint(payload: RuleCreate):
    """Create a new alert rule."""
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    start_time = time.time()

    logger.info("POST /rules request received", extra={"symbol": payload.symbol})

    try:
        rule = create_rule_service(
            symbol=payload.symbol,
            threshold=payload.threshold,
            is_above=payload.is_above,
            webhook_url=payload.webhook_url,
            cooldown_seconds=payload.cooldown_seconds,
            enabled=payload.enabled,
        )
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "POST /rules completed",
            extra={"symbol": payload.symbol, "duration_ms": duration_ms, "status_code": 200},
        )
        clear_trace_id()
        return rule
    except ValueError as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            "POST /rules validation error",
            extra={"symbol": payload.symbol, "duration_ms": duration_ms, "status_code": 400},
        )
        clear_trace_id()
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/rules", response_model=List[Rule])
def list_rules_endpoint():
    """List all alert rules."""
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    start_time = time.time()

    logger.debug("GET /rules request received")

    try:
        rules = list_rules_service()
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "GET /rules completed",
            extra={"duration_ms": duration_ms, "rows_affected": len(rules), "status_code": 200},
        )
        clear_trace_id()
        return rules
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to list rules: {str(e)}",
            extra={"duration_ms": duration_ms, "status_code": 500},
        )
        clear_trace_id()
        raise HTTPException(status_code=500, detail="Failed to list rules")


@app.patch("/rules/{rule_id}", response_model=Rule)
def update_rule_endpoint(rule_id: int, payload: RuleUpdate):
    """Update an alert rule."""
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    start_time = time.time()

    logger.info("PATCH /rules request received", extra={"rule_id": rule_id})

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            "PATCH /rules empty update",
            extra={"rule_id": rule_id, "duration_ms": duration_ms, "status_code": 400},
        )
        clear_trace_id()
        raise HTTPException(status_code=400, detail="No updates provided")

    try:
        rule = update_rule_service(rule_id, updates)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "PATCH /rules completed",
            extra={"rule_id": rule_id, "duration_ms": duration_ms, "status_code": 200},
        )
        clear_trace_id()
        return rule
    except ValueError as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            "PATCH /rules validation error",
            extra={"rule_id": rule_id, "duration_ms": duration_ms, "status_code": 400},
        )
        clear_trace_id()
        detail = str(e)
        status_code = 404 if "Rule not found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail)


@app.get("/rules/{rule_id}/deliveries", response_model=List[Delivery])
def rule_deliveries_endpoint(rule_id: int, limit: int = 100):
    """List deliveries for a rule."""
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    start_time = time.time()

    logger.debug("GET /rules/{rule_id}/deliveries request received", extra={"rule_id": rule_id})

    try:
        deliveries = list_rule_deliveries_service(rule_id, limit=limit)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "GET /rules/{rule_id}/deliveries completed",
            extra={"rule_id": rule_id, "duration_ms": duration_ms, "rows_affected": len(deliveries), "status_code": 200},
        )
        clear_trace_id()
        return deliveries
    except ValueError as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            "GET /rules/{rule_id}/deliveries validation error",
            extra={"rule_id": rule_id, "duration_ms": duration_ms, "status_code": 400},
        )
        clear_trace_id()
        detail = str(e)
        status_code = 404 if "Rule not found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail)
