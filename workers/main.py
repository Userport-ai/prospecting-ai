import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.routes import register_tasks
from api.routes import router
from services.django_callback_service import CallbackService
from utils.async_utils import shutdown_thread_pools
from utils.loguru_setup import logger, setup_context_preserving_task_factory, set_trace_context


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    # Initialize on startup
    log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()
    logger.info("Application starting up", 
        environment=os.getenv('ENVIRONMENT', 'development'),
        log_level=log_level,
        version=os.getenv('VERSION', 'unknown')
    )

    setup_context_preserving_task_factory()

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

    # Set trace context for the entire request
    set_trace_context(trace_id=request_id)

    sensitive_headers = ['authorization', 'cookie']
    filtered_headers = {k: v for k, v in request.headers.items() if k.lower() not in sensitive_headers}


    # Add context to logging
    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        client_host=request.client.host if request.client else None,
        headers=dict(filtered_headers)
    )

    start_time = time.time()

    try:
        response = await call_next(request)

        # Log successful response
        logger.info(
            "Request completed",
            status_code=response.status_code,
            duration_ms=int((time.time() - start_time) * 1000)
        )
        return response

    except Exception as e:
        # Log exception details with full traceback
        logger.opt(exception=True).error(
            f"Request failed: {e}",
            duration_ms=int((time.time() - start_time) * 1000)
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