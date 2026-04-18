from __future__ import annotations

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
)


ItemData = dict[str, Any]


def _to_float(value: str | float | None, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    return float(value)


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
        "steamdt_id": (form_data.get("steamdt_id") or "").strip() or None,
        "image_url": (form_data.get("image_url") or DEFAULT_IMAGE_URL).strip(),
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
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        return None
    return _serialize_item(dict(row))


def create_item(form_data: dict[str, Any]) -> int:
    payload = build_item_payload(form_data)
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO items (
                name, category, wear, steamdt_id, image_url, buy_price, sell_price,
                current_price, fee_rate, fee_amount, profit, profit_rate, buy_platform,
                buy_time, sold_time, tradable_at, is_tradable, status, note, created_at, updated_at
            ) VALUES (
                :name, :category, :wear, :steamdt_id, :image_url, :buy_price, :sell_price,
                :current_price, :fee_rate, :fee_amount, :profit, :profit_rate, :buy_platform,
                :buy_time, :sold_time, :tradable_at, :is_tradable, :status, :note, :created_at, :updated_at
            )
            """,
            payload,
        )
        connection.commit()
        return int(cursor.lastrowid)


def update_item(item_id: int, form_data: dict[str, Any]) -> bool:
    existing = get_item(item_id)
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
        connection.execute(
            """
            UPDATE items SET
                name = :name,
                category = :category,
                wear = :wear,
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
        connection.commit()
    return True


def delete_item(item_id: int) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM items WHERE id = ?", (item_id,))
        connection.commit()


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


def _serialize_item(item: ItemData) -> ItemData:
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

def inline_update_item(item_id: int, field: str, value: str) -> bool:
    existing = get_item(item_id)
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
