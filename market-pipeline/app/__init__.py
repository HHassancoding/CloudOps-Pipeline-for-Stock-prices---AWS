"""CloudOps Market Data Pipeline Application."""

from fastapi import Request
import uuid
from .logging_config import set_trace_id, clear_trace_id


async def add_trace_id_middleware(request: Request, call_next):
    """Middleware to inject trace ID for each request.
    
    Args:
        request: FastAPI request object
        call_next: Next middleware/endpoint function
        
    Returns:
        Response from the next handler
    """
    # Generate or extract trace ID from request headers
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    
    # Set trace ID in context for this request
    set_trace_id(trace_id)
    
    try:
        # Add trace ID to response headers for client reference
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
    finally:
        # Clean up trace ID after request
        clear_trace_id()
