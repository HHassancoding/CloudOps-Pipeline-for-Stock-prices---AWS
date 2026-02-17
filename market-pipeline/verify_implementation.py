"""Quick verification script for multi-symbol implementation."""

print("=" * 60)
print("Multi-Symbol Implementation Verification")
print("=" * 60)

# Check imports
try:
    from app.models import PricePoint, SYMBOL_TO_ID, validate_symbol
    print("✓ models.py imports successful")
    print(f"  - Supported symbols: {list(SYMBOL_TO_ID.keys())}")
except Exception as e:
    print(f"✗ models.py import failed: {e}")
    exit(1)

try:
    from app.db import add_price_point, get_price_history, get_last_two, init_db
    print("✓ db.py imports successful")
except Exception as e:
    print(f"✗ db.py import failed: {e}")
    exit(1)

try:
    from app.services import fetch_price, collect_once, check_anomaly
    print("✓ services.py imports successful")
except Exception as e:
    print(f"✗ services.py import failed: {e}")
    exit(1)

try:
    from app.main import app
    print("✓ main.py imports successful")
except Exception as e:
    print(f"✗ main.py import failed: {e}")
    exit(1)

# Check symbol validation
print("\nTesting symbol validation:")
try:
    assert validate_symbol("BTC") == "BTC"
    assert validate_symbol("btc") == "BTC"
    assert validate_symbol("eth") == "ETH"
    print("✓ Symbol validation works correctly")
except Exception as e:
    print(f"✗ Symbol validation failed: {e}")
    exit(1)

try:
    validate_symbol("INVALID")
    print("✗ Invalid symbol should raise ValueError")
    exit(1)
except ValueError as e:
    print(f"✓ Invalid symbol correctly rejected: {str(e)[:50]}...")

# Check PricePoint model
print("\nTesting PricePoint model:")
try:
    from datetime import datetime
    point = PricePoint(
        id=1,
        timestamp=datetime.utcnow(),
        price=50000.0,
        symbol="BTC"
    )
    assert point.symbol == "BTC"
    assert point.price == 50000.0
    print("✓ PricePoint model includes symbol field")
except Exception as e:
    print(f"✗ PricePoint model failed: {e}")
    exit(1)

# Check function signatures
print("\nVerifying function signatures:")
import inspect

# Check add_price_point signature
sig = inspect.signature(add_price_point)
params = list(sig.parameters.keys())
if 'price' in params and 'symbol' in params:
    print(f"✓ add_price_point(price, symbol): {params}")
else:
    print(f"✗ add_price_point signature incorrect: {params}")
    exit(1)

# Check get_price_history signature
sig = inspect.signature(get_price_history)
params = list(sig.parameters.keys())
if 'symbol' in params and 'limit' in params:
    print(f"✓ get_price_history(symbol, limit): {params}")
else:
    print(f"✗ get_price_history signature incorrect: {params}")
    exit(1)

# Check get_last_two signature
sig = inspect.signature(get_last_two)
params = list(sig.parameters.keys())
if 'symbol' in params:
    print(f"✓ get_last_two(symbol): {params}")
else:
    print(f"✗ get_last_two signature incorrect: {params}")
    exit(1)

# Check fetch_price signature
sig = inspect.signature(fetch_price)
params = list(sig.parameters.keys())
if 'symbol' in params:
    print(f"✓ fetch_price(symbol): {params}")
else:
    print(f"✗ fetch_price signature incorrect: {params}")
    exit(1)

# Check API endpoints
print("\nVerifying API endpoints:")
from fastapi import FastAPI
from fastapi.routing import APIRoute

routes = {route.path: route.methods for route in app.routes if isinstance(route, APIRoute)}
print(f"  Available routes:")
for path, methods in routes.items():
    print(f"    {', '.join(methods)} {path}")

expected_routes = {
    "/collect-once/{symbol}": {"POST"},
    "/history/{symbol}": {"GET"},
    "/anomaly/{symbol}": {"GET"},
    "/supported-symbols": {"GET"}
}

for path, methods in expected_routes.items():
    if path in routes and methods.issubset(routes[path]):
        print(f"✓ {', '.join(methods)} {path}")
    else:
        print(f"✗ Missing or incorrect: {', '.join(methods)} {path}")
        exit(1)

print("\n" + "=" * 60)
print("✓ ALL VERIFICATIONS PASSED!")
print("=" * 60)
print("\nNext steps:")
print("1. Delete old database: del prices.db")
print("2. Install dependencies: pip install -r requirements.txt")
print("3. Run server: uvicorn app.main:app --reload")
print("4. Run tests: pytest tests/ -v")
print("5. Visit: http://localhost:8000/docs")
