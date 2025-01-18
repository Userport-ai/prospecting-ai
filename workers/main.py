import logging
import os
import sys
import time
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pythonjsonlogger import jsonlogger

from api.routes import router


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)

        # Add timestamp if not present
        if not log_record.get('timestamp'):
            log_record['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S.%fZ', time.gmtime())

        # Add severity for GCP logging
        log_record['severity'] = record.levelname

        # Add trace ID if available
        if hasattr(record, 'trace_id'):
            log_record['trace_id'] = record.trace_id

        # Add request_id if available
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id

        # Add error details if present
        if record.exc_info:
            log_record['error'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'stacktrace': traceback.format_exception(*record.exc_info)
            }

logger = logging.getLogger()

# Remove any existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

console_handler = logging.StreamHandler(sys.stdout)

formatter = CustomJsonFormatter(
    '%(timestamp)s %(severity)s %(name)s %(message)s'
)
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()
logger.setLevel(getattr(logging, log_level))
logging.getLogger("httpcore").setLevel(logging.WARNING)

app = FastAPI(title="Workers API")

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    # Generate request ID
    request_id = request.headers.get('X-Request-ID', str(time.time()))

    # Add context to logging
    logger.info(
        "Request started",
        extra={
            'request_id': request_id,
            'method': request.method,
            'url': str(request.url),
            'client_host': request.client.host if request.client else None,
            'headers': dict(request.headers)
        }
    )

    start_time = time.time()

    try:
        response = await call_next(request)

        # Log successful response
        logger.info(
            "Request completed",
            extra={
                'request_id': request_id,
                'status_code': response.status_code,
                'duration_ms': int((time.time() - start_time) * 1000)
            }
        )
        return response

    except Exception as e:
        # Log exception details
        logger.exception(
            "Request failed",
            extra={
                'request_id': request_id,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'duration_ms': int((time.time() - start_time) * 1000)
            }
        )

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "type": type(e).__name__,
                "request_id": request_id
            }
        )

# Include router
app.include_router(router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    logger.info("Health check endpoint called")
    return {"status": "healthy"}

# Log application startup
logger.info("Application starting up", extra={
    'environment': os.getenv('ENVIRONMENT', 'development'),
    'log_level': log_level,
    'version': os.getenv('VERSION', 'unknown')
})

# Add shutdown logging
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down")