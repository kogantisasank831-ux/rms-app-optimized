"""FastAPI app factory: CORS, request-id middleware, exception handlers, routers.

API base path: /api/v1. Envelope + RMS-E-* error codes per LLD 5.1.
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import AppError, error_body
from app.db.session import engine
from app.routers import agents as agents_router
from app.routers import applications as applications_router
from app.routers import auth as auth_router
from app.routers import candidates as candidates_router
from app.routers import careers as careers_router
from app.routers import files as files_router
from app.routers import health as health_router
from app.routers import dashboard as dashboard_router
from app.routers import interviews as interviews_router
from app.routers import offers as offers_router
from app.routers import rrfs as rrfs_router
from app.routers import skills as skills_router
from app.routers import users as users_router

API_PREFIX = "/api/v1"
_log = logging.getLogger("rms.main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Startup: nothing to warm up (engine/pool are lazy).
    yield
    # Shutdown: gracefully close pooled connections so we don't leave idle backends lingering
    # on the shared Postgres server across restarts.
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="TCG Digital RMS API",
        version="0.1.0",
        description="Recruitment Management System — hackathon build (Team T-07).",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # --- exception handlers -> error envelope (LLD 5.1) ---
    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # keep only JSON-safe fields (pydantic v2 errors() may carry exception objects in ctx)
        details = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body("RMS-E-4001", "Validation failed", details),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        # log the full traceback server-side for diagnosis; never leak it to the client
        _log.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_body("RMS-E-5000", "Internal server error"),
        )

    # --- routers ---
    app.include_router(health_router.router, prefix=API_PREFIX)
    app.include_router(auth_router.router, prefix=API_PREFIX)
    app.include_router(files_router.router, prefix=API_PREFIX)
    app.include_router(skills_router.router, prefix=API_PREFIX)
    app.include_router(rrfs_router.router, prefix=API_PREFIX)
    app.include_router(candidates_router.router, prefix=API_PREFIX)
    app.include_router(applications_router.router, prefix=API_PREFIX)
    app.include_router(interviews_router.router, prefix=API_PREFIX)
    app.include_router(offers_router.router, prefix=API_PREFIX)
    app.include_router(dashboard_router.router, prefix=API_PREFIX)
    app.include_router(agents_router.router, prefix=API_PREFIX)
    app.include_router(users_router.router, prefix=API_PREFIX)
    app.include_router(careers_router.router, prefix=API_PREFIX)

    return app


app = create_app()
