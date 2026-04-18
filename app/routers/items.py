from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates

from app.core.constants import CATEGORY_OPTIONS, STATUS_OPTIONS, WEAR_OPTIONS
from app.core.item_logic import format_form_datetime, now_local
from app.services.backup_service import backup_database_if_exists
from app.services.item_service import clone_item, create_item, delete_item, get_item, list_items, update_item, inline_update_item


BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/items")


def _redirect_to_login() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=302)


def _require_user(request: Request) -> str | None:
    return request.session.get("username")


def _build_item_form_context(item: dict | None = None) -> dict:
    current_buy_time = format_form_datetime(now_local().strftime("%Y-%m-%d %H:%M:%S"))
    defaults = {
        "name": "",
        "category": "其他",
        "wear": "无磨损",
        "steamdt_id": "",
        "image_url": "",
        "buy_price": "",
        "sell_price": "",
        "current_price": "",
        "fee_rate": "0.01",
        "fee_amount": "",
        "buy_platform": "",
        "buy_time": current_buy_time,
        "status": "in_stock",
        "note": "",
    }
    if item:
        defaults.update(
            {
                "name": item.get("name", ""),
                "category": item.get("category", "其他"),
                "wear": item.get("wear", "无磨损"),
                "steamdt_id": item.get("steamdt_id") or "",
                "image_url": item.get("image_url", ""),
                "buy_price": item.get("buy_price", ""),
                "sell_price": item.get("sell_price") if item.get("sell_price") is not None else "",
                "current_price": item.get("current_price", ""),
                "fee_rate": item.get("fee_rate", "0.01"),
                "fee_amount": item.get("fee_amount") if item.get("fee_amount") else "",
                "buy_platform": item.get("buy_platform", ""),
                "buy_time": item.get("buy_time_form", current_buy_time),
                "status": item.get("status", "in_stock"),
                "note": item.get("note", ""),
            }
        )
    return defaults


STATUS_OPTIONS_EXTENDED = [
    ("in_stock", "在库 (全部)"),
    ("tradable", "在库 (可售)"),
    ("cooling", "冷却中"),
    ("sold", "已售"),
    ("withdrawn", "撤回"),
]

@router.get("", response_class=HTMLResponse)
async def items_page(
    request: Request,
    search: str = "",
    status: str = "",
    category: str = "",
    start_date: str = "",
    end_date: str = "",
    message: str = "",
) -> Response:
    username = _require_user(request)
    if not username:
        return _redirect_to_login()

    items = list_items(
        search=search, 
        status=status, 
        category=category, 
        start_date=start_date, 
        end_date=end_date
    )
    return templates.TemplateResponse(
        request=request,
        name="items_list.html",
        context={
            "username": username,
            "items": items,
            "search": search,
            "status_filter": status,
            "category_filter": category,
            "start_date": start_date,
            "end_date": end_date,
            "status_options": STATUS_OPTIONS_EXTENDED,
            "category_options": CATEGORY_OPTIONS,
            "wear_options": WEAR_OPTIONS,
            "message": message,
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_item_page(request: Request, clone_id: int | None = None) -> Response:
    username = _require_user(request)
    if not username:
        return _redirect_to_login()

    item = get_item(clone_id) if clone_id else None
    form_data = _build_item_form_context(item)
    title = "复制并编辑饰品" if clone_id else "新增饰品"
    return templates.TemplateResponse(
        request=request,
        name="item_form.html",
        context={
            "username": username,
            "form_title": title,
            "submit_label": "保存饰品",
            "form_action": "/items",
            "item": form_data,
            "wear_options": WEAR_OPTIONS,
            "status_options": STATUS_OPTIONS,
            "category_options": CATEGORY_OPTIONS,
            "created_at_text": item.get("created_at_display") if item else "保存后自动生成",
            "tradable_at_text": item.get("tradable_at_display") if item else "保存后自动计算",
            "is_tradable_text": item.get("is_tradable_text") if item else "保存后自动判断",
        },
    )


@router.post("")
async def create_item_submit(
    request: Request,
    name: str = Form(...),
    category: str = Form(...),
    wear: str = Form(...),
    steamdt_id: str = Form(""),
    image_url: str = Form(""),
    buy_price: str = Form(...),
    fee_rate: str = Form("0.01"),
    fee_amount: str = Form(""),
    buy_platform: str = Form(""),
    buy_time: str = Form(""),
    status: str = Form("in_stock"),
    note: str = Form(""),
) -> Response:
    if not _require_user(request):
        return _redirect_to_login()

    create_item(
        {
            "name": name,
            "category": category,
            "wear": wear,
            "steamdt_id": steamdt_id,
            "image_url": image_url,
            "buy_price": buy_price,
            "sell_price": "",
            "current_price": buy_price,
            "fee_rate": fee_rate,
            "fee_amount": fee_amount,
            "buy_platform": buy_platform,
            "buy_time": buy_time,
            "status": status,
            "note": note,
        }
    )
    return RedirectResponse(url="/items?message=饰品已新增", status_code=303)


@router.get("/{item_id}/edit", response_class=HTMLResponse)
async def edit_item_page(request: Request, item_id: int) -> Response:
    username = _require_user(request)
    if not username:
        return _redirect_to_login()

    item = get_item(item_id)
    if not item:
        return RedirectResponse(url="/items?message=未找到饰品", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="item_form.html",
        context={
            "username": username,
            "form_title": "编辑饰品",
            "submit_label": "保存修改",
            "form_action": f"/items/{item_id}/edit",
            "item": _build_item_form_context(item),
            "wear_options": WEAR_OPTIONS,
            "status_options": STATUS_OPTIONS,
            "category_options": CATEGORY_OPTIONS,
            "created_at_text": item.get("created_at_display"),
            "tradable_at_text": item.get("tradable_at_display"),
            "is_tradable_text": item.get("is_tradable_text"),
        },
    )


@router.post("/{item_id}/edit")
async def edit_item_submit(
    request: Request,
    item_id: int,
    name: str = Form(...),
    category: str = Form(...),
    wear: str = Form(...),
    steamdt_id: str = Form(""),
    image_url: str = Form(""),
    buy_price: str = Form(...),
    current_price: str = Form(""),
    fee_rate: str = Form("0.01"),
    fee_amount: str = Form(""),
    buy_platform: str = Form(""),
    buy_time: str = Form(""),
    status: str = Form("in_stock"),
    note: str = Form(""),
) -> Response:
    if not _require_user(request):
        return _redirect_to_login()

    # Get existing to preserve sell_price
    existing = get_item(item_id)
    sell_price = existing.get("sell_price") if existing else None

    updated = update_item(
        item_id,
        {
            "name": name,
            "category": category,
            "wear": wear,
            "steamdt_id": steamdt_id,
            "image_url": image_url,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "current_price": current_price,
            "fee_rate": fee_rate,
            "fee_amount": fee_amount,
            "buy_platform": buy_platform,
            "buy_time": buy_time,
            "status": status,
            "note": note,
        },
    )
    message = "饰品已更新" if updated else "未找到饰品"
    return RedirectResponse(url=f"/items?message={message}", status_code=303)


@router.get("/{item_id}/json")
async def get_item_json(request: Request, item_id: int) -> Response:
    if not _require_user(request):
        raise HTTPException(status_code=401, detail="未登录")
        
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="未找到饰品")
        
    return JSONResponse(item)

@router.post("/{item_id}/delete")
async def delete_item_submit(request: Request, item_id: int) -> Response:
    if not _require_user(request):
        return _redirect_to_login()

    delete_item(item_id)
    return RedirectResponse(url="/items?message=饰品已删除", status_code=303)


@router.post("/{item_id}/clone")
async def clone_item_submit(request: Request, item_id: int) -> Response:
    if not _require_user(request):
        return _redirect_to_login()

    new_id = clone_item(item_id)
    message = "饰品已克隆" if new_id else "未找到饰品"
    return RedirectResponse(url=f"/items?message={message}", status_code=303)


@router.post("/{item_id}/inline")
async def inline_update_submit(
    request: Request,
    item_id: int,
    field: str = Form(...),
    value: str = Form(""),
) -> Response:
    if not _require_user(request):
        raise HTTPException(status_code=401, detail="未登录")
        
    success = inline_update_item(item_id, field, value)
    if not success:
        raise HTTPException(status_code=400, detail="更新失败")
        
    return JSONResponse({"success": True})


@router.post("/backup")
async def backup_now(request: Request) -> Response:
    if not _require_user(request):
        return _redirect_to_login()

    backup_path = backup_database_if_exists()
    message = "数据库已备份" if backup_path else "当前没有可备份的数据文件"
    return RedirectResponse(url=f"/items?message={message}", status_code=303)
