from .models import PricePoint, SYMBOL_TO_ID, validate_symbol
from .db import add_price_point, get_price_history, get_last_two
import requests


def fetch_price(symbol: str) -> float:
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
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if coingecko_id not in data:
            raise ValueError(f"No price data returned for {symbol} ({coingecko_id})")
            
        return data[coingecko_id]['usd']
    except requests.exceptions.Timeout:
        raise requests.RequestException(f"Timeout fetching price for {symbol}")
    except requests.exceptions.RequestException as e:
        raise requests.RequestException(f"Failed to fetch price for {symbol}: {str(e)}")


def collect_once(symbol: str):
    """Collect and store a single price point for a cryptocurrency symbol.
    
    Args:
        symbol: Cryptocurrency symbol (e.g., "BTC", "ETH")
        
    Returns:
        PricePoint: The stored price point
    """
    normalized_symbol = validate_symbol(symbol)
    price = fetch_price(normalized_symbol)
    point = add_price_point(price, normalized_symbol)
    return point


def check_anomaly(symbol: str):
    """Check for price anomaly by comparing the last two price points.
    
    Args:
        symbol: Cryptocurrency symbol (e.g., "BTC", "ETH")
        
    Returns:
        dict: Anomaly detection result with price information
    """
    normalized_symbol = validate_symbol(symbol)
    last_two = get_last_two(normalized_symbol)
    
    if len(last_two) < 2:
        return {
            "anomaly": False, 
            "message": "Not enough data points", 
            "symbol": normalized_symbol
        }
    
    diff = abs(last_two[0].price - last_two[1].price)
    threshold = 100  # Example threshold for anomaly detection
    is_anomaly = diff >= threshold
    
    return {
        "anomaly": is_anomaly,
        "symbol": normalized_symbol,
        "latest_price": last_two[0].price,
        "second_last_price": last_two[1].price,
        "price_difference": diff,
    }