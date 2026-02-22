from .models import PricePoint, SYMBOL_TO_ID, validate_symbol
from .db import add_price_point, get_price_history, get_last_two
import requests
import time
import logging
import random
import threading
from typing import Optional
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