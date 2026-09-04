import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.models
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger, request_id_var
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.scripts.seed_data import apply_seed_data

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema ensured (create_all).")

        async with AsyncSessionLocal() as db:
            await apply_seed_data(db)
        logger.info("Seed data applied.")
    except Exception:
        logger.exception("Database startup step failed.")
        raise

    yield

    await engine.dispose()
    logger.info("Database engine disposed.")


app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.middleware("http")
async def log_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    request_id = uuid.uuid4().hex
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("%s %s failed after %.1fms", request.method, request.url.path, duration_ms)
        raise
    else:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %s (%.1fms)", request.method, request.url.path, response.status_code, duration_ms
        )
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(token)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
