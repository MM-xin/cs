from __future__ import annotations

import csv
import io
from urllib.parse import quote_plus
from datetime import datetime, timedelta
from typing import Any

from app.core.config import DEFAULT_FEE_RATE, DEFAULT_IMAGE_URL
from app.core.database import get_connection
from app.core.item_logic import (
    calculate_is_tradable,
    calculate_profit_fields,
    calculate_remaining_time,
    calculate_tradable_at,
    format_datetime,
    format_form_datetime,
    now_local,
    parse_datetime,
)


ItemData = dict[str, Any]
TradeData = dict[str, Any]


def _to_float(value: str | float | None, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    return float(value)


def _build_image_url_by_name(name: str) -> str:
    short_name = (name or "CS2").strip()[:18] or "CS2"
    return f"https://placehold.co/120x90?text={quote_plus(short_name)}"


def build_item_payload(
    form_data: dict[str, Any],
    existing_created_at: str | None = None,
    existing_sold_time: str | None = None,
    existing_status: str | None = None,
) -> ItemData:
    current_time = now_local().strftime("%Y-%m-%d %H:%M:%S")
    buy_time = form_data.get("buy_time") or current_time
    tradable_at = calculate_tradable_at(buy_time)
    is_tradable = 1 if calculate_is_tradable(tradable_at) else 0

    buy_price = _to_float(form_data.get("buy_price"), 0.0) or 0.0
    sell_price = _to_float(form_data.get("sell_price"))
    current_price = _to_float(form_data.get("current_price"), buy_price) or buy_price
    fee_rate = DEFAULT_FEE_RATE
    fee_amount = _to_float(form_data.get("fee_amount"))
    sold_time_input = form_data.get("sold_time")
    sold_time = format_datetime(sold_time_input)
    if sell_price is not None:
        if not sold_time:
            sold_time = existing_sold_time or current_time
    else:
        sold_time = None

    explicit_status = form_data.get("status")
    if explicit_status in {"in_stock", "sold", "withdrawn"}:
        status = explicit_status
    elif existing_status:
        status = existing_status
    else:
        status = "sold" if sell_price is not None else "in_stock"

    resolved_fee_amount, profit, profit_rate = calculate_profit_fields(
        buy_price=buy_price,
        current_price=current_price,
        sell_price=sell_price,
        fee_rate=fee_rate,
        fee_amount=fee_amount,
        status=status,
    )

    return {
        "name": (form_data.get("name") or "").strip(),
        "category": (form_data.get("category") or "其他").strip(),
        "wear": (form_data.get("wear") or "无磨损").strip(),
        "market_hash_name": (form_data.get("market_hash_name") or "").strip() or None,
        "steamdt_id": (form_data.get("steamdt_id") or "").strip() or None,
        "image_url": ((form_data.get("image_url") or "").strip() or _build_image_url_by_name((form_data.get("name") or "").strip()) or DEFAULT_IMAGE_URL),
        "buy_price": round(buy_price, 2),
        "sell_price": round(sell_price, 2) if sell_price is not None else None,
        "current_price": round(current_price, 2),
        "fee_rate": round(fee_rate, 4),
        "fee_amount": resolved_fee_amount,
        "profit": profit,
        "profit_rate": profit_rate,
        "buy_platform": (form_data.get("buy_platform") or "").strip(),
        "buy_time": format_datetime(buy_time) or current_time,
        "sold_time": sold_time,
        "tradable_at": tradable_at,
        "is_tradable": is_tradable,
        "status": status,
        "note": (form_data.get("note") or "").strip(),
        "created_at": existing_created_at or current_time,
        "updated_at": current_time,
    }


def _normalize_trade_time(value: str | None, fallback: str) -> str:
    normalized = format_datetime(value)
    return normalized or fallback


def _create_trade(
    connection,
    *,
    item_id: int,
    trade_type: str,
    amount: float,
    fee_amount: float,
    trade_time: str,
    source: str = "system",
    note: str = "",
) -> None:
    now = now_local().strftime("%Y-%m-%d %H:%M:%S")
    net_amount = round(amount - fee_amount, 2)
    connection.execute(
        """
        INSERT INTO trades (
            item_id, trade_type, amount, fee_amount, net_amount, trade_time, source, note, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            item_id,
            trade_type,
            round(amount, 2),
            round(fee_amount, 2),
            net_amount,
            trade_time,
            source,
            note.strip() or None,
            now,
            now,
        ),
    )


def _serialize_trade(trade: TradeData) -> TradeData:
    labels = {
        "buy": "买入",
        "sell": "卖出",
        "withdraw": "撤回",
        "fee_adjust": "手续费调整",
    }
    trade["trade_time_display"] = format_datetime(trade.get("trade_time"))
    trade["created_at_display"] = format_datetime(trade.get("created_at"))
    trade["trade_type_label"] = labels.get(trade.get("trade_type"), trade.get("trade_type"))
    return trade


def _get_item_raw(item_id: int) -> ItemData | None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        return None
    return dict(row)


def _ensure_baseline_trades(connection, item_id: int, item: ItemData) -> None:
    count = connection.execute("SELECT COUNT(1) AS c FROM trades WHERE item_id = ?", (item_id,)).fetchone()["c"]
    if count:
        return

    created_at = item.get("created_at") or now_local().strftime("%Y-%m-%d %H:%M:%S")
    _create_trade(
        connection,
        item_id=item_id,
        trade_type="buy",
        amount=float(item.get("buy_price") or 0),
        fee_amount=0,
        trade_time=_normalize_trade_time(item.get("buy_time"), created_at),
        note="初始化买入流水",
    )

    sell_price = item.get("sell_price")
    if sell_price in (None, ""):
        return

    status = item.get("status")
    trade_type = "withdraw" if status == "withdrawn" else "sell"
    fee = 0.0 if trade_type == "withdraw" else float(item.get("fee_amount") or 0)
    note = "初始化撤回流水" if trade_type == "withdraw" else "初始化卖出流水"
    _create_trade(
        connection,
        item_id=item_id,
        trade_type=trade_type,
        amount=float(sell_price),
        fee_amount=fee,
        trade_time=_normalize_trade_time(item.get("sold_time"), created_at),
        note=note,
    )


def _sync_trades_after_update(connection, item_id: int, before: ItemData, after: ItemData) -> None:
    updated_at = after.get("updated_at") or now_local().strftime("%Y-%m-%d %H:%M:%S")
    before_buy = float(before.get("buy_price") or 0)
    after_buy = float(after.get("buy_price") or 0)
    before_sell = before.get("sell_price")
    after_sell = after.get("sell_price")
    before_status = str(before.get("status") or "")
    after_status = str(after.get("status") or "")
    before_fee = float(before.get("fee_amount") or 0)
    after_fee = float(after.get("fee_amount") or 0)

    if before_buy != after_buy:
        _create_trade(
            connection,
            item_id=item_id,
            trade_type="buy",
            amount=after_buy,
            fee_amount=0,
            trade_time=_normalize_trade_time(after.get("buy_time"), updated_at),
            note=f"买入价调整: {before_buy:.2f} -> {after_buy:.2f}",
        )

    sell_price_changed = before_sell != after_sell
    status_to_withdrawn = before_status != "withdrawn" and after_status == "withdrawn"

    if sell_price_changed and after_sell not in (None, ""):
        after_sell_value = float(after_sell)
        is_withdraw = after_status == "withdrawn"
        trade_type = "withdraw" if is_withdraw else "sell"
        fee_amount = 0.0 if is_withdraw else after_fee
        note = "首次卖出" if before_sell in (None, "") and not is_withdraw else "卖出价调整"
        if is_withdraw:
            note = "撤回入账"
        _create_trade(
            connection,
            item_id=item_id,
            trade_type=trade_type,
            amount=after_sell_value,
            fee_amount=fee_amount,
            trade_time=_normalize_trade_time(after.get("sold_time"), updated_at),
            note=note,
        )

    if status_to_withdrawn and after_sell not in (None, "") and not sell_price_changed:
        _create_trade(
            connection,
            item_id=item_id,
            trade_type="withdraw",
            amount=float(after_sell),
            fee_amount=0,
            trade_time=_normalize_trade_time(after.get("sold_time"), updated_at),
            note="状态变更为撤回",
        )

    if before_fee != after_fee and after_status == "sold" and not sell_price_changed:
        _create_trade(
            connection,
            item_id=item_id,
            trade_type="fee_adjust",
            amount=after_fee,
            fee_amount=0,
            trade_time=_normalize_trade_time(after.get("sold_time"), updated_at),
            note=f"手续费调整: {before_fee:.2f} -> {after_fee:.2f}",
        )


def refresh_runtime_fields() -> None:
    with get_connection() as connection:
        rows = connection.execute("SELECT id, tradable_at FROM items").fetchall()
        for row in rows:
            is_tradable = 1 if calculate_is_tradable(row["tradable_at"]) else 0
            connection.execute(
                "UPDATE items SET is_tradable = ?, updated_at = updated_at WHERE id = ?",
                (is_tradable, row["id"]),
            )
        connection.commit()


def list_items(
    search: str = "",
    status: str = "",
    category: str = "",
    start_date: str = "",
    end_date: str = "",
    sold_start_date: str = "",
    sold_end_date: str = "",
) -> list[ItemData]:
    refresh_runtime_fields()
    query = "SELECT * FROM items WHERE 1 = 1"
    params: list[Any] = []

    if search:
        query += " AND name LIKE ?"
        params.append(f"%{search.strip()}%")
    if status:
        if status == "tradable":
            query += " AND status = 'in_stock' AND is_tradable = 1"
        elif status == "cooling":
            query += " AND status = 'in_stock' AND is_tradable = 0"
        else:
            query += " AND status = ?"
            params.append(status)
    if category:
        query += " AND category = ?"
        params.append(category)
    if start_date:
        query += " AND buy_time >= ?"
        params.append(f"{start_date} 00:00:00")
    if end_date:
        query += " AND buy_time <= ?"
        params.append(f"{end_date} 23:59:59")
    if sold_start_date:
        query += " AND sold_time >= ?"
        params.append(f"{sold_start_date} 00:00:00")
    if sold_end_date:
        query += " AND sold_time <= ?"
        params.append(f"{sold_end_date} 23:59:59")

    query += " ORDER BY buy_time DESC, id DESC"

    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
    return [_serialize_item(dict(row)) for row in rows]


def get_item(item_id: int) -> ItemData | None:
    refresh_runtime_fields()
    item = _get_item_raw(item_id)
    if not item:
        return None
    return _serialize_item(item)


def create_item(form_data: dict[str, Any]) -> int:
    # 新增时如果用户没指定图片，尝试按名字/market_hash_name 抓取并缓存到本地
    if not (form_data.get("image_url") or "").strip():
        try:
            from app.services.image_service import ensure_local_image

            local_url = ensure_local_image(
                (form_data.get("name") or "").strip(),
                (form_data.get("market_hash_name") or "").strip() or None,
            )
            if local_url:
                form_data = {**form_data, "image_url": local_url}
        except Exception:
            pass

    payload = build_item_payload(form_data)
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO items (
                name, category, wear, market_hash_name, steamdt_id, image_url, buy_price, sell_price,
                current_price, fee_rate, fee_amount, profit, profit_rate, buy_platform,
                buy_time, sold_time, tradable_at, is_tradable, status, note, created_at, updated_at
            ) VALUES (
                :name, :category, :wear, :market_hash_name, :steamdt_id, :image_url, :buy_price, :sell_price,
                :current_price, :fee_rate, :fee_amount, :profit, :profit_rate, :buy_platform,
                :buy_time, :sold_time, :tradable_at, :is_tradable, :status, :note, :created_at, :updated_at
            )
            """,
            payload,
        )
        item_id = int(cursor.lastrowid)
        _create_trade(
            connection,
            item_id=item_id,
            trade_type="buy",
            amount=float(payload.get("buy_price") or 0),
            fee_amount=0,
            trade_time=_normalize_trade_time(payload.get("buy_time"), payload["created_at"]),
            note="新增饰品自动记录买入",
        )
        if payload.get("sell_price") is not None:
            status = payload.get("status")
            is_withdraw = status == "withdrawn"
            _create_trade(
                connection,
                item_id=item_id,
                trade_type="withdraw" if is_withdraw else "sell",
                amount=float(payload["sell_price"]),
                fee_amount=0 if is_withdraw else float(payload.get("fee_amount") or 0),
                trade_time=_normalize_trade_time(payload.get("sold_time"), payload["updated_at"]),
                note="新增饰品已包含卖出记录",
            )
        connection.commit()
        return item_id


def create_items_bulk(items: list[dict[str, Any]]) -> list[int]:
    ids: list[int] = []
    for form_data in items or []:
        ids.append(create_item(form_data))
    return ids


def bulk_sell(item_ids: list[int], sell_price: float, sold_time: str) -> dict[str, Any]:
    """把一批在库饰品的卖出价/卖出时间统一写入，并追加卖出流水。"""
    updated_ids: list[int] = []
    skipped: list[dict[str, Any]] = []
    sold_time_norm = (sold_time or "").strip() or now_local().strftime("%Y-%m-%d %H:%M:%S")
    try:
        price_val = float(sell_price)
    except (TypeError, ValueError):
        raise ValueError("卖出价必须是数字")
    if price_val < 0:
        raise ValueError("卖出价不能为负")

    for item_id in item_ids or []:
        existing = _get_item_raw(item_id)
        if not existing:
            skipped.append({"id": item_id, "reason": "未找到"})
            continue
        if existing.get("status") == "sold":
            skipped.append({"id": item_id, "reason": "已售，跳过"})
            continue
        form_data = {
            "name": existing.get("name"),
            "category": existing.get("category"),
            "wear": existing.get("wear"),
            "market_hash_name": existing.get("market_hash_name"),
            "steamdt_id": existing.get("steamdt_id"),
            "image_url": existing.get("image_url"),
            "buy_price": existing.get("buy_price"),
            "sell_price": price_val,
            "current_price": existing.get("current_price"),
            "fee_rate": existing.get("fee_rate"),
            "buy_platform": existing.get("buy_platform"),
            "buy_time": existing.get("buy_time"),
            "sold_time": sold_time_norm,
            "status": "sold",
            "note": existing.get("note"),
        }
        if update_item(item_id, form_data):
            updated_ids.append(item_id)
        else:
            skipped.append({"id": item_id, "reason": "更新失败"})
    return {"updated": updated_ids, "skipped": skipped}


def update_item(item_id: int, form_data: dict[str, Any]) -> bool:
    existing = _get_item_raw(item_id)
    if not existing:
        return False

    payload = build_item_payload(
        form_data,
        existing_created_at=existing["created_at"],
        existing_sold_time=existing.get("sold_time"),
        existing_status=existing.get("status"),
    )
    payload["id"] = item_id

    with get_connection() as connection:
        _ensure_baseline_trades(connection, item_id, existing)
        connection.execute(
            """
            UPDATE items SET
                name = :name,
                category = :category,
                wear = :wear,
                market_hash_name = :market_hash_name,
                steamdt_id = :steamdt_id,
                image_url = :image_url,
                buy_price = :buy_price,
                sell_price = :sell_price,
                current_price = :current_price,
                fee_rate = :fee_rate,
                fee_amount = :fee_amount,
                profit = :profit,
                profit_rate = :profit_rate,
                buy_platform = :buy_platform,
                buy_time = :buy_time,
                sold_time = :sold_time,
                tradable_at = :tradable_at,
                is_tradable = :is_tradable,
                status = :status,
                note = :note,
                created_at = :created_at,
                updated_at = :updated_at
            WHERE id = :id
            """,
            payload,
        )
        _sync_trades_after_update(connection, item_id, existing, payload)
        connection.commit()
    return True


def delete_item(item_id: int) -> dict[str, int]:
    """级联删除饰品及其所有关联数据（流水 + 历史审计）。返回各表删除行数。"""
    with get_connection() as connection:
        connection.execute("BEGIN")
        trades_deleted = connection.execute(
            "DELETE FROM trades WHERE item_id = ?", (item_id,)
        ).rowcount
        audits_deleted = connection.execute(
            "DELETE FROM audit_logs WHERE item_id = ?", (item_id,)
        ).rowcount
        items_deleted = connection.execute(
            "DELETE FROM items WHERE id = ?", (item_id,)
        ).rowcount
        connection.commit()
    return {
        "items": int(items_deleted or 0),
        "trades": int(trades_deleted or 0),
        "audit_logs": int(audits_deleted or 0),
    }


def clone_item(item_id: int) -> int | None:
    existing = get_item(item_id)
    if not existing:
        return None

    clone_form_data = {
        key: existing.get(key)
        for key in (
            "name",
            "category",
            "wear",
            "market_hash_name",
            "steamdt_id",
            "image_url",
            "buy_price",
            "sell_price",
            "current_price",
            "fee_rate",
            "fee_amount",
            "buy_platform",
            "buy_time",
            "sold_time",
            "status",
            "note",
        )
    }
    return create_item(clone_form_data)


def list_item_trades(item_id: int) -> list[TradeData]:
    with get_connection() as connection:
        item_row = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not item_row:
            return []
        item = dict(item_row)
        _ensure_baseline_trades(connection, item_id, item)
        rows = connection.execute(
            """
            SELECT * FROM trades
            WHERE item_id = ?
            ORDER BY trade_time DESC, id DESC
            """,
            (item_id,),
        ).fetchall()
        connection.commit()
    return [_serialize_trade(dict(row)) for row in rows]


def _serialize_item(item: ItemData) -> ItemData:
    if not item.get("image_url"):
        item["image_url"] = _build_image_url_by_name(item.get("name") or "")
    item["buy_time_display"] = format_datetime(item.get("buy_time"))
    item["buy_time_form"] = format_form_datetime(item.get("buy_time"))
    item["sold_time_display"] = format_datetime(item.get("sold_time"))
    item["sold_time_form"] = format_form_datetime(item.get("sold_time"))
    item["tradable_at_display"] = format_datetime(item.get("tradable_at"))
    item["remaining_time_display"] = calculate_remaining_time(item.get("tradable_at"))
    item["created_at_display"] = format_datetime(item.get("created_at"))
    item["created_at_form"] = format_form_datetime(item.get("created_at"))
    item["is_tradable"] = bool(item.get("is_tradable"))
    item["is_tradable_text"] = "可售" if item["is_tradable"] else "冷却中"
    item["profit_percent"] = round((item.get("profit_rate") or 0) * 100, 2)
    item["fee_rate_percent"] = round((item.get("fee_rate") or 0) * 100, 2)
    item["price_updated_at_display"] = format_datetime(item.get("price_updated_at"))
    prev_price = item.get("previous_price")
    current_price = item.get("current_price")
    if prev_price is None or current_price is None:
        item["price_change"] = None
        item["price_change_percent"] = None
    else:
        try:
            prev_v = float(prev_price)
            cur_v = float(current_price)
            item["price_change"] = round(cur_v - prev_v, 2)
            item["price_change_percent"] = round((cur_v - prev_v) / prev_v * 100, 2) if prev_v else None
        except (TypeError, ValueError):
            item["price_change"] = None
            item["price_change_percent"] = None
    
    if item.get("status") == "in_stock":
        if item["is_tradable"]:
            item["status_label"] = "在库"
            item["status_class"] = "badge-status-in_stock"
        else:
            item["status_label"] = "冷却中"
            item["status_class"] = "badge-status-cooling"
    elif item.get("status") == "sold":
        item["status_label"] = "已售"
        item["status_class"] = "badge-status-sold"
    elif item.get("status") == "withdrawn":
        item["status_label"] = "撤回"
        item["status_class"] = "badge-status-withdrawn"
    else:
        item["status_label"] = item.get("status")
        item["status_class"] = "badge-neutral"
        
    item["profit_class"] = "positive" if (item.get("profit") or 0) >= 0 else "negative"
    return item

def recalculate_all() -> dict[str, Any]:
    """Re-apply profit/fee logic on all items. Useful when formula or fee_rate changes."""
    refresh_runtime_fields()
    updated = 0
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM items").fetchall()
        for row in rows:
            item = dict(row)
            buy_price = float(item.get("buy_price") or 0)
            sell_price = item.get("sell_price")
            current_price = float(item.get("current_price") or buy_price)
            fee_rate = float(item.get("fee_rate") or DEFAULT_FEE_RATE)
            status = item.get("status") or "in_stock"
            fee_amount, profit, profit_rate = calculate_profit_fields(
                buy_price=buy_price,
                current_price=current_price,
                sell_price=float(sell_price) if sell_price not in (None, "") else None,
                fee_rate=fee_rate,
                fee_amount=float(item.get("fee_amount") or 0),
                status=status,
            )
            connection.execute(
                """
                UPDATE items SET
                    fee_amount = ?,
                    profit = ?,
                    profit_rate = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    fee_amount,
                    profit,
                    profit_rate,
                    now_local().strftime("%Y-%m-%d %H:%M:%S"),
                    item["id"],
                ),
            )
            updated += 1
        connection.commit()
    return {"updated": updated}


def _aggregate(rows: list[Any], key: str) -> float:
    return round(sum(float(row[key] or 0) for row in rows), 2)


def dashboard_summary() -> dict[str, Any]:
    refresh_runtime_fields()
    with get_connection() as connection:
        items = [dict(row) for row in connection.execute("SELECT * FROM items").fetchall()]

    now = now_local()
    thirty_days_ago = now - timedelta(days=30)

    in_stock = [it for it in items if it.get("status") == "in_stock"]
    sold = [it for it in items if it.get("status") == "sold"]
    withdrawn = [it for it in items if it.get("status") == "withdrawn"]
    cooling = [it for it in in_stock if not it.get("is_tradable")]

    inventory_cost = _aggregate(in_stock, "buy_price")
    inventory_market = round(
        sum(float(it.get("current_price") or it.get("buy_price") or 0) for it in in_stock), 2
    )
    floating_pnl = round(inventory_market - inventory_cost, 2)

    realized_profit = _aggregate(sold, "profit")
    realized_revenue = round(
        sum(float(it.get("sell_price") or 0) for it in sold), 2
    )
    realized_fee = _aggregate(sold, "fee_amount")

    cooling_cost = _aggregate(cooling, "buy_price")

    recent_sold = [
        it
        for it in sold
        if (parsed := parse_datetime(it.get("sold_time"))) and parsed >= thirty_days_ago
    ]
    recent_profit = _aggregate(recent_sold, "profit")
    recent_revenue = round(sum(float(it.get("sell_price") or 0) for it in recent_sold), 2)

    # monthly trend (最近 12 个月): 根据 sold_time 统计
    monthly: dict[str, dict[str, float]] = {}
    for i in range(11, -1, -1):
        month = (now.replace(day=1) - timedelta(days=30 * i)).strftime("%Y-%m")
        monthly[month] = {"month": month, "profit": 0.0, "revenue": 0.0, "count": 0}
    for it in sold:
        parsed = parse_datetime(it.get("sold_time"))
        if not parsed:
            continue
        key = parsed.strftime("%Y-%m")
        if key in monthly:
            monthly[key]["profit"] += float(it.get("profit") or 0)
            monthly[key]["revenue"] += float(it.get("sell_price") or 0)
            monthly[key]["count"] += 1
    trend = []
    for m in sorted(monthly.keys()):
        entry = monthly[m]
        trend.append(
            {
                "month": entry["month"],
                "profit": round(entry["profit"], 2),
                "revenue": round(entry["revenue"], 2),
                "count": int(entry["count"]),
            }
        )

    top_profit = sorted(sold, key=lambda x: float(x.get("profit") or 0), reverse=True)[:5]
    top_loss = sorted(sold, key=lambda x: float(x.get("profit") or 0))[:5]

    def _brief(it: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": it.get("id"),
            "name": it.get("name"),
            "profit": round(float(it.get("profit") or 0), 2),
            "buy_price": round(float(it.get("buy_price") or 0), 2),
            "sell_price": round(float(it.get("sell_price") or 0), 2),
            "sold_time_display": format_datetime(it.get("sold_time")),
        }

    return {
        "counts": {
            "total": len(items),
            "in_stock": len(in_stock),
            "sold": len(sold),
            "withdrawn": len(withdrawn),
            "cooling": len(cooling),
        },
        "inventory": {
            "cost": inventory_cost,
            "market_value": inventory_market,
            "floating_pnl": floating_pnl,
            "cooling_cost": cooling_cost,
            "cooling_ratio": round(cooling_cost / inventory_cost, 4) if inventory_cost else 0.0,
        },
        "realized": {
            "profit": realized_profit,
            "revenue": realized_revenue,
            "fee": realized_fee,
            "count": len(sold),
        },
        "recent_30d": {
            "profit": recent_profit,
            "revenue": recent_revenue,
            "count": len(recent_sold),
        },
        "monthly_trend": trend,
        "top_profit": [_brief(it) for it in top_profit if float(it.get("profit") or 0) > 0],
        "top_loss": [_brief(it) for it in top_loss if float(it.get("profit") or 0) < 0],
    }


EXPORT_COLUMNS = [
    ("id", "ID"),
    ("name", "名称"),
    ("category", "类型"),
    ("wear", "磨损"),
    ("buy_price", "买入价"),
    ("sell_price", "卖出价"),
    ("fee_amount", "手续费"),
    ("profit", "利润"),
    ("profit_percent", "利润率%"),
    ("status_label", "状态"),
    ("buy_time_display", "买入时间"),
    ("sold_time_display", "卖出时间"),
    ("tradable_at_display", "可售时间"),
    ("buy_platform", "平台"),
    ("note", "备注"),
]


def export_items_csv(filters: dict[str, Any] | None = None) -> str:
    filters = filters or {}
    items = list_items(
        search=filters.get("search", ""),
        status=filters.get("status", ""),
        category=filters.get("category", ""),
        start_date=filters.get("start_date", ""),
        end_date=filters.get("end_date", ""),
        sold_start_date=filters.get("sold_start_date", ""),
        sold_end_date=filters.get("sold_end_date", ""),
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([header for _, header in EXPORT_COLUMNS])
    for it in items:
        writer.writerow([it.get(key, "") if it.get(key) is not None else "" for key, _ in EXPORT_COLUMNS])
    return buffer.getvalue()


def inline_update_item(item_id: int, field: str, value: str) -> bool:
    existing = _get_item_raw(item_id)
    if not existing:
        return False
    
    allowed_fields = ["buy_price", "sell_price"]
    if field not in allowed_fields:
        return False
        
    form_data = dict(existing)
    
    if field in ["buy_price", "sell_price"]:
        form_data[field] = value if value else None
        
        # If selling, update status automatically
        if field == "sell_price":
            form_data["fee_amount"] = None  # Force recalculation of fee
            if value:
                form_data["status"] = "sold"
                if not existing.get("sold_time"):
                    form_data["sold_time"] = now_local().strftime("%Y-%m-%d %H:%M:%S")
            elif not value and existing["status"] == "sold":
                form_data["status"] = "in_stock"
                form_data["sold_time"] = None
    else:
        form_data[field] = value
        
    return update_item(item_id, form_data)
