from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.services.auth_service import verify_user


BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    if request.session.get("username"):
        return RedirectResponse(url="/items", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None},
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> Response:
    if verify_user(username=username, password=password):
        request.session["username"] = username
        return RedirectResponse(url="/items", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "用户名或密码错误"},
        status_code=401,
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> Response:
    username = request.session.get("username")
    if not username:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"username": username},
    )


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
