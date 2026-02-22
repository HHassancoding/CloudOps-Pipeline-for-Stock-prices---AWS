# CloudOps Market Data Pipeline – AI Agent Guidelines

## Project Overview

A Python-based prototype market data pipeline for cryptocurrency prices. The system fetches live data from CoinGecko API, stores price history in PostgreSQL/SQLite, and provides FastAPI endpoints to query anomalies and historical data. Built to transition from local development to AWS cloud deployment.

**Supported Symbols:** BTC, ETH, SOL, ADA, DOT

---

## Code Style & Conventions

### Python Formatting

- **Version:** Python 3.10+
- **Formatter:** Plain Python (no Black/Ruff enforcement; follow PEP 8)
- **Imports:** Standard library → third-party → local modules
- **Type Hints:** Use `Optional[T]`, `List[T]`, `Dict[K,V]` from `typing`; leverage `sqlmodel` for ORM types

### Logging Pattern

All modules use **structured JSON logging** via `JSONFormatter` in [logging_config.py](app/logging_config.py). Every important operation logs with:
- Trace ID (per-request context variable)
- Duration in milliseconds for performance tracking
- Custom fields: `symbol`, `status_code`, `rows_affected`, `client_ip`

**Example:**
```python
logger.info(
    "Price point inserted for {symbol}",
    extra={"symbol": symbol, "duration_ms": duration_ms, "rows_affected": 1}
)
```

Do NOT use plain `print()` statements; always use the logger from `get_logger(__name__)`.

### Error Handling

- **Service layer** (`services.py`): Raise domain-specific exceptions (`ValueError`, `requests.RequestException`)
- **Endpoint layer** (`main.py`): Catch exceptions and convert to `HTTPException` with appropriate status codes
- **Database layer** (`db.py`): Log errors with full context; let caller decide how to handle

---

## Architecture

### Core Components

1. **Models** ([models.py](app/models.py))
   - `PricePoint`: SQLModel table with `id`, `timestamp`, `price`, `symbol`
   - `SYMBOL_TO_ID`: Dict mapping cryptocurrency symbols to CoinGecko API IDs
   - `validate_symbol()`: Normalizes and validates input symbols

2. **Services** ([services.py](app/services.py))
   - `fetch_price(symbol, client_ip)`: Fetches current price from CoinGecko with retry/backoff logic
   - `collect_once(symbol, client_ip)`: Wraps fetch + insert into one transaction
   - `check_anomaly(symbol)`: Detects price movements using last two data points
   - Rate limiting: `FixedWindowRateLimiter` (100 req/60s per client IP)
   - Backoff strategy: Exponential with jitter (0.5s → 5s, 0.2s jitter)

3. **Database** ([db.py](db.py))
   - `init_db()`: Creates tables at startup via `SQLModel.metadata.create_all()`
   - `add_price_point(price, symbol)`: Insert single record with UTC timestamp
   - `get_price_history(symbol, limit=100)`: Fetch latest N records ordered by timestamp DESC
   - `get_last_two(symbol)`: For anomaly detection

4. **API Layer** ([main.py](app/main.py))
   - Lifespan handler: Initializes DB on app startup
   - `POST /collect-once/{symbol}`: Collect & store single price point
   - Middleware: Injects trace ID for request tracing
   - Error responses: 400 (invalid symbol), 503 (API failure), 500 (DB error)

### Data Flow

```
CoinGecko API
      ↓ (fetch_price)
   [Backoff & Rate Limit]
      ↓
 collect_once()
      ↓
 add_price_point() → [PostgreSQL/SQLite]
      ↓
 HTTP 200 + PricePoint JSON
```

---

## Build and Test

### Prerequisites

- Python 3.10+
- Virtual environment (`.venv`)
- PostgreSQL (production) or SQLite (local dev)

### Setup

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# or: source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r market-pipeline/requirements.txt
```

### Run Locally

```bash
cd market-pipeline
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing

```bash
# Run all tests
pytest market-pipeline/tests/

# Run specific test class
pytest market-pipeline/tests/test_endpoints.py::TestCollectOnceEndpoint -v

# Run with coverage
pytest market-pipeline/tests/ --cov=app --cov-report=term-only
```

**Test Environment:** In-memory SQLite via `conftest.py` fixtures; mocks external API calls.

### Verification

```bash
python market-pipeline/verify_implementation.py
```

Checks endpoint availability, database connectivity, and basic functionality.

---

## Project Conventions

### Symbol Handling

- Always **normalize to uppercase** via `validate_symbol()` before processing
- Map symbols to CoinGecko IDs from `SYMBOL_TO_ID` dict
- Reject unsupported symbols with `ValueError("Unsupported symbol: ...")`

### Trace ID Pattern

Every HTTP request receives a unique UUID trace ID:
1. Generated in endpoint handler: `trace_id = str(uuid.uuid4())`
2. Set in context: `set_trace_id(trace_id)`
3. Automatically included in all logs
4. Cleared after response: `clear_trace_id()`

### Rate Limiting & Backoff

- **Global Rate Limiter:** 100 requests / 60 seconds per client IP
- **Per-request Backoff:** 2^attempt * 0.5s, max 5s, jitter ±0.2s
- **Retryable Statuses:** 429, 500, 502, 503, 504
- **Max Retries:** 3 attempts

If rate limit exceeded, raise `requests.RequestException("Rate limit exceeded")`.

### Database Timestamps

- Always use **UTC**: `datetime.now(timezone.utc)`
- Never assume local timezone
- Store in ISO format for logs

---

## Integration Points

### External Dependencies

- **CoinGecko API:** `https://api.coingecko.com/api/v3/simple/price`
  - Public (no auth required)
  - Rate limit: ~50 req/min (we use 100/60s conservatively)
  - Timeout: 5 seconds

- **PostgreSQL** (production via `DATABASE_URL` env var)
  - Connection pooling via SQLAlchemy
  - Credentials in `.env` file (never commit)

- **SQLite** (local dev, path: `./prices.db`)
  - In-memory for tests

### Environment Variables

```bash
# In .env or deploy config
DATABASE_URL=postgresql://user:pass@host:5432/market_db
LOG_LEVEL=INFO  # Or DEBUG, WARNING, ERROR
```

---

## Security

### Sensitive Areas

1. **Database Credentials** ([db.py](app/db.py))
   - Load from `.env` via `load_dotenv()`
   - Never hardcode or log `DATABASE_URL`
   - Log only the scheme part: `DATABASE_URL.split('@')[0]`

2. **External API Calls** ([services.py](app/services.py))
   - Public API (no secrets)
   - Validate symbol input to prevent injection
   - Use 5s timeout to prevent DoS

3. **Trace ID** ([logging_config.py](app/logging_config.py))
   - Context variable (thread-safe via contextvars)
   - Cleared after request to prevent leaks

### Input Validation

- Symbol: Whitelist check against `SYMBOL_TO_ID.keys()`
- Price: No negative prices; respect CoinGecko response format
- Timestamps: Always UTC, reject future dates in anomaly detection

---

## Key Files Reference

| File | Purpose |
|------|---------|
| [app/main.py](app/main.py) | FastAPI app, endpoints, lifespan, error handling |
| [app/services.py](app/services.py) | Business logic: fetch, collect, anomaly detection, rate limiting |
| [app/models.py](app/models.py) | SQLModel ORM, symbol validation, API mappings |
| [app/db.py](app/db.py) | Database operations: init, insert, query |
| [app/logging_config.py](app/logging_config.py) | JSON logging, trace ID context, formatters |
| [tests/conftest.py](tests/conftest.py) | Pytest fixtures, in-memory DB, mocks |
| [tests/test_endpoints.py](tests/test_endpoints.py) | Endpoint unit tests with mocked services |
| [requirements.txt](requirements.txt) | Dependency list (FastAPI, SQLModel, etc.) |

