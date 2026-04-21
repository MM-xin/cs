from __future__ import annotations

import os
from pathlib import Path
from secrets import token_urlsafe

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.database import initialize_database
from app.core.logger import logger, setup_logging
from app.routers.api import router as api_router
from app.services.scheduler import shutdown_scheduler, start_scheduler


BASE_DIR = Path(__file__).resolve().parent

setup_logging()

app = FastAPI(title="CS 饰品管理工具")

# SESSION_SECRET 环境变量优先，保证容器重启登录态不丢；未设置则每次启动随机
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET") or token_urlsafe(32),
    max_age=60 * 60 * 24,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:9000",
        "http://localhost:9000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(api_router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error(f"HTTPException {exc.status_code} on {request.url.path}: {exc.detail}")
    else:
        logger.info(f"HTTPException {exc.status_code} on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "success": False},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": "参数校验失败", "errors": exc.errors(), "success": False},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试", "success": False},
    )


@app.on_event("startup")
async def startup_event() -> None:
    initialize_database()
    start_scheduler()
    logger.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    shutdown_scheduler()
    logger.info("Application shutdown complete")


@app.get("/")
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "service": "CS 饰品管理工具 - Backend API",
            "docs": "/docs",
            "health": "/api/health",
            "frontend": "Vue 3 SPA（开发: http://localhost:9000，部署: http://<host>:8080）",
        }
    )
