import logging
import os
import sys
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pythonjsonlogger import jsonlogger

from api.routes import register_tasks
from api.routes import router
from services.django_callback_service import CallbackService
from utils.async_utils import shutdown_thread_pools
from utils.tracing import (
    TraceContextFilter,
    get_trace_id,
    get_job_id,
    get_account_id,
    get_lead_id,
    get_task_name,
    set_trace_context,
    extract_trace_context_from_payload
)


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)

        # Add timestamp if not present
        if not log_record.get('timestamp'):
            log_record['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S.%fZ', time.gmtime())

        # Add severity for GCP logging
        log_record['severity'] = record.levelname

        # Add trace context fields
        if hasattr(record, 'trace_id') and record.trace_id:
            log_record['trace_id'] = record.trace_id
            
        if hasattr(record, 'job_id') and record.job_id:
            log_record['job_id'] = record.job_id
            
        if hasattr(record, 'account_id') and record.account_id:
            log_record['account_id'] = record.account_id
            
        if hasattr(record, 'lead_id') and record.lead_id:
            log_record['lead_id'] = record.lead_id
            
        if hasattr(record, 'task_name') and record.task_name:
            log_record['task_name'] = record.task_name

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

# Add trace context filter to inject context into log records
trace_filter = TraceContextFilter()
logger.addFilter(trace_filter)

logger.addHandler(console_handler)

log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()
logger.setLevel(getattr(logging, log_level))
logging.getLogger("httpcore").setLevel(logging.WARNING)

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    # Initialize on startup
    logger.info("Application starting up", extra={
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'log_level': log_level,
        'version': os.getenv('VERSION', 'unknown')
    })
    fastapi_app.state.callback_service = await CallbackService.get_instance()
    await register_tasks()

    try:
        yield
    finally:
        # Cleanup on shutdown
        logger.info("Lifespan: Application is shutting down")
        # cleanup thread_pools
        await shutdown_thread_pools()

        callback_service = getattr(fastapi_app.state, 'callback_service', None)
        if callback_service:
            await callback_service.cleanup()

app = FastAPI(title="Workers API", lifespan=lifespan)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    # Generate request ID
    request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    sensitive_headers = ['authorization', 'cookie']
    filtered_headers = {k: v for k, v in request.headers.items() if k.lower() not in sensitive_headers}
    
    # Extract trace context from headers or query params if available
    trace_id = request.headers.get('X-Trace-ID') or request.query_params.get('trace_id')
    
    # Initialize trace context
    # For task endpoints, we'll extract and set the context from the payload later in routes.py
    set_trace_context(
        trace_id=trace_id,
        # Other fields will be set from payload for task endpoints
    )
    
    # Add context to logging
    logger.info(
        "Request started",
        extra={
            'request_id': request_id,
            'method': request.method,
            'url': str(request.url),
            'client_host': request.client.host if request.client else None,
            'headers': dict(filtered_headers)
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
        
        # Add trace_id to response headers for client tracking
        trace_id = get_trace_id()
        if trace_id:
            response.headers['X-Trace-ID'] = trace_id
            
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
                "request_id": request_id,
                "trace_id": get_trace_id()
            }
        )

# Include router
app.include_router(router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    logger.info("Health check endpoint called")
    return {"status": "healthy"}