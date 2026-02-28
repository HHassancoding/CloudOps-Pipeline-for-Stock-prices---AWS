from .models import PricePoint, SYMBOL_TO_ID, validate_symbol, Rule, Delivery
from .db import (
    add_price_point,
    get_price_history,
    get_last_two,
    create_rule,
    list_rules,
    update_rule,
    get_rule,
    get_rule_deliveries,
)
import requests
import time
import logging
import random
import threading
from typing import Optional, List
from .logging_config import get_logger

logger = get_logger(__name__)

RATE_LIMIT_MAX_REQUESTS = 100
RATE_LIMIT_WINDOW_SECONDS = 60
BACKOFF_MAX_RETRIES = 3
BACKOFF_BASE_DELAY_SECONDS = 0.5
BACKOFF_MAX_DELAY_SECONDS = 5.0
BACKOFF_JITTER_SECONDS = 0.2
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class FixedWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, time_fn=time.time):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.time_fn = time_fn
        self._buckets = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self.time_fn()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or now - bucket["start"] >= self.window_seconds:
                self._buckets[key] = {"start": now, "count": 1}
                return True
            if bucket["count"] < self.max_requests:
                bucket["count"] += 1
                return True
            return False


_rate_limiter = FixedWindowRateLimiter(RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS)


def _compute_backoff_delay(attempt: int) -> float:
    delay = BACKOFF_BASE_DELAY_SECONDS * (2 ** attempt)
    delay = min(delay, BACKOFF_MAX_DELAY_SECONDS)
    jitter = random.uniform(0, BACKOFF_JITTER_SECONDS)
    return delay + jitter


def fetch_price(symbol: str, client_ip: Optional[str] = None) -> float:
    """Fetch current price for a cryptocurrency symbol from CoinGecko API.
    
    Args:
        symbol: Cryptocurrency symbol (e.g., "BTC", "ETH")
        
    Returns:
        Current price in USD
        
    Raises:
        ValueError: If symbol is not supported
        requests.RequestException: If API call fails
    """
    # Validate and normalize symbol
    normalized_symbol = validate_symbol(symbol)
    coingecko_id = SYMBOL_TO_ID[normalized_symbol]
    
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coingecko_id,
        "vs_currencies": "usd"
    }
    
    client_key = client_ip or "unknown"

    logger.debug(
        f"Fetching price from CoinGecko for {normalized_symbol} (ID: {coingecko_id})",
        extra={"symbol": normalized_symbol, "client_ip": client_key}
    )

    attempt = 0
    while True:
        if not _rate_limiter.allow(client_key):
            logger.warning(
                "Rate limit exceeded for CoinGecko fetch",
                extra={"symbol": normalized_symbol, "client_ip": client_key}
            )
            raise requests.RequestException("Rate limit exceeded")

        start_time = time.time()
        try:
            response = requests.get(url, params=params, timeout=5)
            status_code = response.status_code

            if status_code in RETRYABLE_STATUS_CODES:
                if attempt >= BACKOFF_MAX_RETRIES:
                    duration_ms = (time.time() - start_time) * 1000
                    logger.error(
                        f"Retry limit reached for {normalized_symbol} with status {status_code}",
                        extra={"symbol": normalized_symbol, "duration_ms": duration_ms, "status_code": status_code, "client_ip": client_key}
                    )
                    raise requests.RequestException(
                        f"Failed to fetch price for {symbol}: status {status_code}"
                    )

                delay = _compute_backoff_delay(attempt)
                logger.warning(
                    "Retrying CoinGecko fetch after backoff",
                    extra={
                        "symbol": normalized_symbol,
                        "status_code": status_code,
                        "attempt": attempt + 1,
                        "delay_ms": delay * 1000,
                        "client_ip": client_key,
                    },
                )
                time.sleep(delay)
                attempt += 1
                continue

            response.raise_for_status()
            data = response.json()

            if coingecko_id not in data:
                logger.error(
                    f"No price data returned for {normalized_symbol} ({coingecko_id})",
                    extra={"symbol": normalized_symbol, "client_ip": client_key}
                )
                raise ValueError(f"No price data returned for {symbol} ({coingecko_id})")

            price = data[coingecko_id]["usd"]
            duration_ms = (time.time() - start_time) * 1000

            log_level = "warning" if duration_ms > 5000 else "info"
            logger.log(
                logging.WARNING if log_level == "warning" else logging.INFO,
                f"Price fetched successfully for {normalized_symbol}: ${price}",
                extra={
                    "symbol": normalized_symbol,
                    "duration_ms": duration_ms,
                    "status_code": 200,
                    "client_ip": client_key,
                    "attempts": attempt + 1,
                },
            )
            return price

        except requests.exceptions.Timeout:
            duration_ms = (time.time() - start_time) * 1000
            if attempt >= BACKOFF_MAX_RETRIES:
                logger.error(
                    f"Timeout fetching price for {normalized_symbol} (took >{duration_ms:.0f}ms)",
                    extra={"symbol": normalized_symbol, "duration_ms": duration_ms, "client_ip": client_key}
                )
                raise requests.RequestException(f"Timeout fetching price for {symbol}")

            delay = _compute_backoff_delay(attempt)
            logger.warning(
                "Timeout fetching price; retrying after backoff",
                extra={
                    "symbol": normalized_symbol,
                    "attempt": attempt + 1,
                    "delay_ms": delay * 1000,
                    "client_ip": client_key,
                },
            )
            time.sleep(delay)
            attempt += 1
        except requests.exceptions.RequestException as e:
            duration_ms = (time.time() - start_time) * 1000
            if isinstance(e, requests.exceptions.HTTPError):
                status_code = e.response.status_code if e.response else None
                if status_code not in RETRYABLE_STATUS_CODES:
                    logger.error(
                        f"Non-retryable HTTP error for {normalized_symbol}: {str(e)}",
                        extra={
                            "symbol": normalized_symbol,
                            "duration_ms": duration_ms,
                            "status_code": status_code,
                            "client_ip": client_key,
                        },
                        exc_info=True,
                    )
                    raise requests.RequestException(
                        f"Failed to fetch price for {symbol}: {str(e)}"
                    )
            if attempt >= BACKOFF_MAX_RETRIES:
                logger.error(
                    f"API request failed for {normalized_symbol}: {str(e)}",
                    extra={"symbol": normalized_symbol, "duration_ms": duration_ms, "client_ip": client_key},
                    exc_info=True,
                )
                raise requests.RequestException(
                    f"Failed to fetch price for {symbol}: {str(e)}"
                )

            delay = _compute_backoff_delay(attempt)
            logger.warning(
                "Request error fetching price; retrying after backoff",
                extra={
                    "symbol": normalized_symbol,
                    "attempt": attempt + 1,
                    "delay_ms": delay * 1000,
                    "client_ip": client_key,
                },
            )
            time.sleep(delay)
            attempt += 1


def collect_once(symbol: str, client_ip: Optional[str] = None):
    """Collect and store a single price point for a cryptocurrency symbol.
    
    Args:
        symbol: Cryptocurrency symbol (e.g., "BTC", "ETH")
        
    Returns:
        PricePoint: The stored price point
    """
    logger.info(f"Starting price collection for {symbol}", extra={"symbol": symbol})
    try:
        normalized_symbol = validate_symbol(symbol)
        price = fetch_price(normalized_symbol, client_ip=client_ip)
        point = add_price_point(price, normalized_symbol)
        logger.info(
            f"Price collected and stored for {normalized_symbol}: ${price}",
            extra={"symbol": normalized_symbol}
        )
        return point
    except Exception as e:
        logger.error(
            f"Failed to collect price for {symbol}: {str(e)}",
            extra={"symbol": symbol},
            exc_info=True
        )
        raise


def check_anomaly(symbol: str):
    """Check for price anomaly by comparing the last two price points.
    
    Args:
        symbol: Cryptocurrency symbol (e.g., "BTC", "ETH")
        
    Returns:
        dict: Anomaly detection result with price information
    """
    logger.debug(f"Checking for anomalies for {symbol}", extra={"symbol": symbol})
    
    try:
        normalized_symbol = validate_symbol(symbol)
        last_two = get_last_two(normalized_symbol)
        
        if len(last_two) < 2:
            logger.info(
                f"Insufficient data for anomaly detection for {normalized_symbol}",
                extra={"symbol": normalized_symbol, "data_points": len(last_two)}
            )
            return {
                "anomaly": False, 
                "message": "Not enough data points", 
                "symbol": normalized_symbol
            }
        
        diff = abs(last_two[0].price - last_two[1].price)
        threshold = 100  # Example threshold for anomaly detection
        is_anomaly = diff >= threshold
        
        log_level = logging.WARNING if is_anomaly else logging.INFO
        logger.log(
            log_level,
            f"Anomaly check for {normalized_symbol}: diff=${diff:.2f}, threshold=${threshold}, anomaly={is_anomaly}",
            extra={"symbol": normalized_symbol}
        )
        
        return {
            "anomaly": is_anomaly,
            "symbol": normalized_symbol,
            "latest_price": last_two[0].price,
            "second_last_price": last_two[1].price,
            "price_difference": diff,
        }
    except ValueError as e:
        logger.error(
            f"Error checking anomaly for {symbol}: {str(e)}",
            extra={"symbol": symbol},
            exc_info=True
        )
        raise


def _validate_rule_inputs(
    symbol: str,
    threshold: float,
    is_above: bool,
    webhook_url: str,
    cooldown_seconds: int,
) -> str:
    normalized_symbol = validate_symbol(symbol)
    if threshold <= 0:
        raise ValueError("Threshold must be greater than 0")
    if cooldown_seconds < 0:
        raise ValueError("Cooldown must be 0 or greater")
    if not webhook_url or not webhook_url.startswith("http"):
        raise ValueError("Webhook URL must be a valid http/https URL")
    if not isinstance(is_above, bool):
        raise ValueError("Direction must be a boolean is_above")
    return normalized_symbol


def create_rule_service(
    symbol: str,
    threshold: float,
    is_above: bool,
    webhook_url: str,
    cooldown_seconds: int,
    enabled: bool = True,
) -> Rule:
    """Create a new rule after validation."""
    start_time = time.time()
    normalized_symbol = _validate_rule_inputs(
        symbol=symbol,
        threshold=threshold,
        is_above=is_above,
        webhook_url=webhook_url,
        cooldown_seconds=cooldown_seconds,
    )

    rule = create_rule(
        symbol=normalized_symbol,
        threshold=threshold,
        is_above=is_above,
        webhook_url=webhook_url,
        cooldown_seconds=cooldown_seconds,
        enabled=enabled,
    )
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        "Rule created via service",
        extra={
            "symbol": normalized_symbol,
            "rule_id": rule.id,
            "duration_ms": duration_ms,
            "rows_affected": 1,
        },
    )
    return rule


def list_rules_service() -> List[Rule]:
    """List all rules."""
    start_time = time.time()
    rules = list_rules()
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        "Rules listed via service",
        extra={"duration_ms": duration_ms, "rows_affected": len(rules)},
    )
    return rules


def update_rule_service(rule_id: int, updates: dict) -> Rule:
    """Update rule fields after validation."""
    allowed_fields = {"enabled", "threshold", "cooldown_seconds", "webhook_url", "is_above"}
    invalid_fields = set(updates.keys()) - allowed_fields
    if invalid_fields:
        raise ValueError(f"Unsupported update fields: {', '.join(sorted(invalid_fields))}")

    if "threshold" in updates and updates["threshold"] is not None:
        if updates["threshold"] <= 0:
            raise ValueError("Threshold must be greater than 0")
    if "cooldown_seconds" in updates and updates["cooldown_seconds"] is not None:
        if updates["cooldown_seconds"] < 0:
            raise ValueError("Cooldown must be 0 or greater")
    if "webhook_url" in updates and updates["webhook_url"] is not None:
        if not updates["webhook_url"].startswith("http"):
            raise ValueError("Webhook URL must be a valid http/https URL")
    if "is_above" in updates and updates["is_above"] is not None:
        if not isinstance(updates["is_above"], bool):
            raise ValueError("Direction must be a boolean is_above")

    rule = update_rule(rule_id, updates)
    if not rule:
        raise ValueError(f"Rule not found: {rule_id}")
    return rule


def list_rule_deliveries_service(rule_id: int, limit: int = 100) -> List[Delivery]:
    """List deliveries for a rule."""
    if limit <= 0:
        raise ValueError("Limit must be greater than 0")

    existing_rule = get_rule(rule_id)
    if not existing_rule:
        raise ValueError(f"Rule not found: {rule_id}")

    deliveries = get_rule_deliveries(rule_id, limit=limit)
    logger.info(
        "Rule deliveries listed via service",
        extra={"rule_id": rule_id, "rows_affected": len(deliveries)},
    )
    return deliveries