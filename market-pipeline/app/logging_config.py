import logging
import logging.handlers
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from contextvars import ContextVar
import sys

# Context variable for storing trace ID per request
trace_id_context: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add trace ID if present
        trace_id = trace_id_context.get()
        if trace_id:
            log_obj["trace_id"] = trace_id

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Add custom fields if present in the record
        custom_fields = ["symbol", "duration_ms", "status_code", "request_id", "rows_affected"]
        for field in custom_fields:
            if hasattr(record, field):
                log_obj[field] = getattr(record, field)

        return json.dumps(log_obj)


class TraceIDFilter(logging.Filter):
    """Add trace ID to all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        trace_id = trace_id_context.get()
        if trace_id:
            record.trace_id = trace_id
        return True


class LoggingConfig:
    """Centralized logging configuration for production deployment."""

    _instance: Optional["LoggingConfig"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if LoggingConfig._initialized:
            return

        LoggingConfig._initialized = True
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

    def setup_logging(
        self,
        name: str,
        level: int = logging.INFO,
        use_json: bool = True,
        enable_file_handler: bool = True,
    ) -> logging.Logger:
        """Configure logger with console and file handlers.

        Args:
            name: Logger name (usually __name__)
            level: Logging level
            use_json: Use JSON formatting for structured logs
            enable_file_handler: Write logs to rotating file

        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Prevent duplicate handlers
        if logger.hasHandlers():
            return logger

        # Add trace ID filter
        logger.addFilter(TraceIDFilter())

        # Format selection
        if use_json:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler (rotating)
        if enable_file_handler:
            log_file = self.log_dir / f"{name.replace('.', '_')}.log"
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def get_logger(self, name: str) -> logging.Logger:
        """Get or create logger for a module."""
        return logging.getLogger(name)


# Singleton accessor
def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance."""
    config = LoggingConfig()
    return config.setup_logging(name)


def set_trace_id(trace_id: str) -> None:
    """Set trace ID for current request context."""
    trace_id_context.set(trace_id)


def get_trace_id() -> Optional[str]:
    """Get current trace ID from context."""
    return trace_id_context.get()


def clear_trace_id() -> None:
    """Clear trace ID from context."""
    trace_id_context.set(None)
