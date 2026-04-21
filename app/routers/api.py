from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from app.core.constants import CATEGORY_OPTIONS
from app.services.audit_service import list_audit_logs, record_audit
from app.services.backup_service import backup_database_if_exists
from app.services.auth_service import verify_user
from app.services.item_service import (
    bulk_sell,
    clone_item,
    create_item,
    create_items_bulk,
    dashboard_summary,
    delete_item,
    export_items_csv,
    get_item,
    inline_update_item,
    list_item_trades,
    list_items,
    recalculate_all,
    update_item,
)
from app.services.steamdt_service import (
    SteamDTError,
    ping as steamdt_ping,
    pick_preferred_price,
    query_price,
)
from app.services.catalog_service import (
    catalog_stats,
    lookup_market_hash_name,
    search_catalog,
    search_catalog_paginated,
    sync_catalog_from_steamdt,
)
from app.services.price_service import (
    price_config,
    refresh_price_for_item,
    refresh_prices,
)


router = APIRouter(prefix="/api", tags=["api"])


def _require_user(request: Request) -> str:
    username = request.session.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="未登录")
    return username


@router.get("/health")
async def api_health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


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


@router.get("/items/export")
async def api_export_items(
    request: Request,
    search: str = "",
    status: str = "",
    category: str = "",
    start_date: str = "",
    end_date: str = "",
    sold_start_date: str = "",
    sold_end_date: str = "",
) -> Response:
    _require_user(request)
    csv_text = export_items_csv(
        {
            "search": search,
            "status": status,
            "category": category,
            "start_date": start_date,
            "end_date": end_date,
            "sold_start_date": sold_start_date,
            "sold_end_date": sold_end_date,
        }
    )
    # 加 UTF-8 BOM 以便 Excel 正确识别中文
    content = "\ufeff" + csv_text
    headers = {
        "Content-Disposition": 'attachment; filename="items_export.csv"',
    }
    return Response(content=content, media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/items/{item_id}")
async def api_get_item(request: Request, item_id: int) -> JSONResponse:
    _require_user(request)
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="未找到饰品")
    return JSONResponse(item)


@router.post("/items")
async def api_create_item(request: Request) -> JSONResponse:
    username = _require_user(request)
    payload: dict[str, Any] = await request.json()
    payload.setdefault("sell_price", "")
    payload.setdefault("current_price", payload.get("buy_price", ""))
    item_id = create_item(payload)
    record_audit(
        action="item.create",
        username=username,
        item_id=item_id,
        detail={"name": payload.get("name"), "buy_price": payload.get("buy_price")},
    )
    return JSONResponse({"success": True, "id": item_id})


@router.post("/items/bulk")
async def api_bulk_create_items(request: Request) -> JSONResponse:
    username = _require_user(request)
    payload: dict[str, Any] = await request.json()
    base = payload.get("base") or {}
    try:
        quantity = int(payload.get("quantity") or 1)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="数量必须为整数")
    if quantity < 1 or quantity > 100:
        raise HTTPException(status_code=400, detail="数量需在 1-100 之间")
    if not (base.get("name") or "").strip():
        raise HTTPException(status_code=400, detail="名称不能为空")
    base.setdefault("sell_price", "")
    base.setdefault("current_price", base.get("buy_price", ""))
    items = [dict(base) for _ in range(quantity)]
    ids = create_items_bulk(items)
    record_audit(
        action="item.create.bulk",
        username=username,
        detail={
            "name": base.get("name"),
            "buy_price": base.get("buy_price"),
            "quantity": quantity,
            "ids": ids,
        },
    )
    return JSONResponse({"success": True, "ids": ids, "count": len(ids)})


@router.post("/items/bulk-sell")
async def api_bulk_sell_items(request: Request) -> JSONResponse:
    username = _require_user(request)
    payload: dict[str, Any] = await request.json()
    item_ids = payload.get("item_ids") or []
    if not isinstance(item_ids, list) or not item_ids:
        raise HTTPException(status_code=400, detail="请至少选择 1 件饰品")
    sell_price = payload.get("sell_price")
    if sell_price in (None, ""):
        raise HTTPException(status_code=400, detail="请填写卖出价")
    sold_time = (payload.get("sold_time") or "").strip()
    try:
        result = bulk_sell([int(i) for i in item_ids], float(sell_price), sold_time)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    record_audit(
        action="item.sell.bulk",
        username=username,
        detail={
            "sell_price": float(sell_price),
            "sold_time": sold_time,
            "requested": len(item_ids),
            "updated": len(result.get("updated") or []),
            "skipped": result.get("skipped"),
        },
    )
    return JSONResponse({"success": True, **result})


@router.put("/items/{item_id}")
async def api_update_item(request: Request, item_id: int) -> JSONResponse:
    username = _require_user(request)
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
    record_audit(
        action="item.update",
        username=username,
        item_id=item_id,
        detail={"fields": list(payload.keys())},
    )
    return JSONResponse({"success": True})


@router.delete("/items/{item_id}")
async def api_delete_item(request: Request, item_id: int) -> JSONResponse:
    username = _require_user(request)
    existing = get_item(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="未找到饰品")
    cascade = delete_item(item_id)
    record_audit(
        action="item.delete",
        username=username,
        item_id=item_id,
        detail={
            "name": existing.get("name"),
            "cascade": cascade,
        },
    )
    return JSONResponse({"success": True, "cascade": cascade})


@router.post("/items/{item_id}/clone")
async def api_clone_item(request: Request, item_id: int) -> JSONResponse:
    username = _require_user(request)
    new_id = clone_item(item_id)
    if not new_id:
        raise HTTPException(status_code=404, detail="未找到饰品")
    record_audit(
        action="item.clone",
        username=username,
        item_id=new_id,
        detail={"from": item_id},
    )
    return JSONResponse({"success": True, "id": new_id})


@router.patch("/items/{item_id}/inline")
async def api_inline_update_item(request: Request, item_id: int) -> JSONResponse:
    username = _require_user(request)
    payload: dict[str, Any] = await request.json()
    field = str(payload.get("field", "")).strip()
    value = str(payload.get("value", ""))
    existing = get_item(item_id)
    prev_value = existing.get(field) if existing else None
    success = inline_update_item(item_id=item_id, field=field, value=value)
    if not success:
        raise HTTPException(status_code=400, detail="更新失败")
    record_audit(
        action="item.inline_update",
        username=username,
        item_id=item_id,
        detail={"field": field, "old": prev_value, "new": value or None},
    )
    return JSONResponse({"success": True, "previous": prev_value})


@router.get("/items/{item_id}/trades")
async def api_list_item_trades(request: Request, item_id: int) -> JSONResponse:
    _require_user(request)
    existing = get_item(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="未找到饰品")
    return JSONResponse({"trades": list_item_trades(item_id)})


@router.post("/items/recalculate")
async def api_recalculate(request: Request) -> JSONResponse:
    username = _require_user(request)
    result = recalculate_all()
    record_audit(
        action="item.recalculate",
        username=username,
        detail=result,
    )
    return JSONResponse({"success": True, **result})


@router.get("/dashboard")
async def api_dashboard(request: Request) -> JSONResponse:
    _require_user(request)
    return JSONResponse(dashboard_summary())


@router.get("/audit-logs")
async def api_audit_logs(request: Request, limit: int = 200) -> JSONResponse:
    _require_user(request)
    return JSONResponse({"logs": list_audit_logs(limit=max(1, min(limit, 1000)))})


@router.get("/steamdt/ping")
async def api_steamdt_ping(request: Request) -> JSONResponse:
    _require_user(request)
    try:
        result = steamdt_ping()
    except SteamDTError as exc:
        raise HTTPException(status_code=502, detail=f"SteamDT 调用失败: {exc}")
    return JSONResponse({"success": True, **result})


@router.get("/steamdt/price")
async def api_steamdt_price(request: Request, name: str) -> JSONResponse:
    _require_user(request)
    try:
        records = query_price(name)
    except SteamDTError as exc:
        raise HTTPException(status_code=502, detail=f"SteamDT 调用失败: {exc}")
    preferred = pick_preferred_price(records)
    return JSONResponse(
        {
            "success": True,
            "market_hash_name": name,
            "preferred": preferred,
            "all_platforms": records,
        }
    )


@router.get("/catalog/stats")
async def api_catalog_stats(request: Request) -> JSONResponse:
    _require_user(request)
    return JSONResponse({"success": True, **catalog_stats()})


@router.get("/catalog/search")
async def api_catalog_search(
    request: Request,
    q: str = "",
    page: int = 1,
    size: int = 20,
    limit: int | None = None,
) -> JSONResponse:
    _require_user(request)
    # 兼容旧调用：传 limit 时退化为不分页（只返回前 limit 条）
    if limit is not None:
        results = search_catalog(q, limit=limit)
        return JSONResponse({"success": True, "items": results, "total": len(results)})
    data = search_catalog_paginated(q, page=page, size=size)
    return JSONResponse({"success": True, **data})


@router.get("/catalog/lookup")
async def api_catalog_lookup(request: Request, name: str) -> JSONResponse:
    _require_user(request)
    market_hash_name = lookup_market_hash_name(name)
    return JSONResponse(
        {
            "success": True,
            "name": name,
            "market_hash_name": market_hash_name,
        }
    )


@router.post("/catalog/sync")
async def api_catalog_sync(request: Request) -> JSONResponse:
    username = _require_user(request)
    try:
        result = sync_catalog_from_steamdt()
    except SteamDTError as exc:
        record_audit(
            action="catalog.sync.manual",
            username=username,
            detail={"error": str(exc)},
            success=False,
        )
        raise HTTPException(status_code=502, detail=f"SteamDT 调用失败: {exc}")
    record_audit(
        action="catalog.sync.manual",
        username=username,
        detail=result,
        success=True,
    )
    return JSONResponse({"success": True, **result})


@router.get("/prices/config")
async def api_prices_config(request: Request) -> JSONResponse:
    _require_user(request)
    return JSONResponse({"success": True, **price_config()})


@router.post("/prices/refresh")
async def api_prices_refresh(request: Request) -> JSONResponse:
    username = _require_user(request)
    try:
        payload = await request.json() if await request.body() else {}
    except Exception:
        payload = {}
    item_ids = payload.get("item_ids") if isinstance(payload, dict) else None
    if item_ids is not None and not isinstance(item_ids, list):
        raise HTTPException(status_code=400, detail="item_ids 必须是数组")
    try:
        result = refresh_prices(item_ids=item_ids)
    except SteamDTError as exc:
        record_audit(
            action="price.refresh.manual",
            username=username,
            detail={"error": str(exc)},
            success=False,
        )
        raise HTTPException(status_code=502, detail=f"SteamDT 调用失败: {exc}")
    record_audit(
        action="price.refresh.manual",
        username=username,
        detail={"updated": result.get("updated"), "skipped": result.get("skipped")},
        success=True,
    )
    return JSONResponse({"success": True, **result})


@router.post("/items/{item_id}/refresh-price")
async def api_item_refresh_price(request: Request, item_id: int) -> JSONResponse:
    username = _require_user(request)
    try:
        result = refresh_price_for_item(item_id)
    except SteamDTError as exc:
        record_audit(
            action="price.refresh.single",
            username=username,
            item_id=item_id,
            detail={"error": str(exc)},
            success=False,
        )
        raise HTTPException(status_code=502, detail=f"SteamDT 调用失败: {exc}")
    if not result.get("updated"):
        record_audit(
            action="price.refresh.single",
            username=username,
            item_id=item_id,
            detail=result,
            success=False,
        )
        raise HTTPException(status_code=404, detail=result.get("error") or "no_price")
    record_audit(
        action="price.refresh.single",
        username=username,
        item_id=item_id,
        detail=result.get("item"),
        success=True,
    )
    return JSONResponse({"success": True, **result})


@router.post("/backup")
async def api_backup(request: Request) -> JSONResponse:
    username = _require_user(request)
    backup_path = backup_database_if_exists()
    record_audit(
        action="backup.manual",
        username=username,
        detail={"backup_path": backup_path},
        success=backup_path is not None,
    )
    return JSONResponse({"success": True, "backup_path": backup_path})
