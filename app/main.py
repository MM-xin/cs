from __future__ import annotations

from pathlib import Path
from secrets import token_urlsafe

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.database import initialize_database
from app.routers.api import router as api_router
from app.routers.auth import router as auth_router
from app.routers.items import router as items_router


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="CS 饰品管理工具")
app.add_middleware(
    SessionMiddleware,
    secret_key=token_urlsafe(32),
    max_age=60 * 60 * 24,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(auth_router)
app.include_router(items_router)
app.include_router(api_router)


@app.on_event("startup")
async def startup_event() -> None:
    initialize_database()


@app.get("/")
async def home() -> RedirectResponse:
    return RedirectResponse(url="/items", status_code=302)
