from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from api.routes import router

import logging
from pythonjsonlogger import jsonlogger

# Configure logging
formatter = jsonlogger.JsonFormatter(
    fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
    json_ensure_ascii=False
)

# Add JSON formatter
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(levelname)s %(name)s %(message)s',
    timestamp=True,
    stack_info=True
)
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.handlers = [logHandler]

app = FastAPI(title="Workers API")

@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.exception(f"Unhandled exception occurred: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "type": type(e).__name__
            }
        )
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
