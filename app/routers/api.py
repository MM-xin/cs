from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.constants import CATEGORY_OPTIONS
from app.services.backup_service import backup_database_if_exists
from app.services.auth_service import verify_user
from app.services.item_service import (
    clone_item,
    create_item,
    delete_item,
    get_item,
    inline_update_item,
    list_items,
    update_item,
)


router = APIRouter(prefix="/api", tags=["api"])


def _require_user(request: Request) -> str:
    username = request.session.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="未登录")
    return username


@router.post("/login")
async def api_login(request: Request) -> JSONResponse:
    payload: dict[str, Any] = await request.json()
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not verify_user(username=username, password=password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    request.session["username"] = username
    return JSONResponse({"success": True, "username": username})


@router.post("/logout")
async def api_logout(request: Request) -> JSONResponse:
    request.session.clear()
    return JSONResponse({"success": True})


@router.get("/me")
async def api_me(request: Request) -> JSONResponse:
    username = _require_user(request)
    return JSONResponse({"username": username})


@router.get("/meta")
async def api_meta(request: Request) -> JSONResponse:
    _require_user(request)
    status_options = [
        {"value": "", "label": "全部"},
        {"value": "in_stock", "label": "在库(全部)"},
        {"value": "tradable", "label": "在库(可售)"},
        {"value": "cooling", "label": "冷却中"},
        {"value": "sold", "label": "已售"},
        {"value": "withdrawn", "label": "撤回"},
    ]
    return JSONResponse(
        {
            "category_options": CATEGORY_OPTIONS,
            "status_options": status_options,
        }
    )


@router.get("/items")
async def api_list_items(
    request: Request,
    search: str = "",
    status: str = "",
    category: str = "",
    start_date: str = "",
    end_date: str = "",
    sold_start_date: str = "",
    sold_end_date: str = "",
) -> JSONResponse:
    _require_user(request)
    data = list_items(
        search=search,
        status=status,
        category=category,
        start_date=start_date,
        end_date=end_date,
        sold_start_date=sold_start_date,
        sold_end_date=sold_end_date,
    )
    return JSONResponse({"items": data})


@router.get("/items/{item_id}")
async def api_get_item(request: Request, item_id: int) -> JSONResponse:
    _require_user(request)
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="未找到饰品")
    return JSONResponse(item)


@router.post("/items")
async def api_create_item(request: Request) -> JSONResponse:
    _require_user(request)
    payload: dict[str, Any] = await request.json()
    payload.setdefault("sell_price", "")
    payload.setdefault("current_price", payload.get("buy_price", ""))
    item_id = create_item(payload)
    return JSONResponse({"success": True, "id": item_id})


@router.put("/items/{item_id}")
async def api_update_item(request: Request, item_id: int) -> JSONResponse:
    _require_user(request)
    payload: dict[str, Any] = await request.json()
    existing = get_item(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="未找到饰品")
    payload.setdefault("sell_price", existing.get("sell_price"))
    payload.setdefault("sold_time", existing.get("sold_time"))
    payload.setdefault("status", existing.get("status"))
    sold_time_input = payload.get("sold_time")
    sell_price_input = payload.get("sell_price")
    if sold_time_input and str(sold_time_input).strip():
        if sell_price_input in (None, ""):
            raise HTTPException(status_code=400, detail="未出售饰品不能设置出售时间")
    updated = update_item(item_id, payload)
    if not updated:
        raise HTTPException(status_code=400, detail="更新失败")
    return JSONResponse({"success": True})


@router.delete("/items/{item_id}")
async def api_delete_item(request: Request, item_id: int) -> JSONResponse:
    _require_user(request)
    delete_item(item_id)
    return JSONResponse({"success": True})


@router.post("/items/{item_id}/clone")
async def api_clone_item(request: Request, item_id: int) -> JSONResponse:
    _require_user(request)
    new_id = clone_item(item_id)
    if not new_id:
        raise HTTPException(status_code=404, detail="未找到饰品")
    return JSONResponse({"success": True, "id": new_id})


@router.patch("/items/{item_id}/inline")
async def api_inline_update_item(request: Request, item_id: int) -> JSONResponse:
    _require_user(request)
    payload: dict[str, Any] = await request.json()
    field = str(payload.get("field", "")).strip()
    value = str(payload.get("value", ""))
    success = inline_update_item(item_id=item_id, field=field, value=value)
    if not success:
        raise HTTPException(status_code=400, detail="更新失败")
    return JSONResponse({"success": True})


@router.post("/backup")
async def api_backup(request: Request) -> JSONResponse:
    _require_user(request)
    backup_path = backup_database_if_exists()
    return JSONResponse({"success": True, "backup_path": backup_path})
