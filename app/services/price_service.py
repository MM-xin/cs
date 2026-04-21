from __future__ import annotations

import time
from typing import Any

from app.core.config import load_steamdt_config
from app.core.database import get_connection
from app.core.item_logic import calculate_profit_fields, format_datetime, now_local
from app.core.logger import logger
from app.services import steamdt_service
from app.services.catalog_service import lookup_market_hash_name

DEFAULT_PLATFORM = "youpin"


def _cfg() -> dict:
    cfg = load_steamdt_config() or {}
    return cfg


def default_platform() -> str:
    return str(_cfg().get("default_platform") or DEFAULT_PLATFORM).lower()


def pick_price(records: list[dict], prefer: str | None = None) -> dict | None:
    """按 default_platform 优先，其次 preferred_platforms 顺序。"""
    if not records:
        return None
    prefer = (prefer or default_platform()).lower()
    by_platform = {str(r.get("platform") or "").lower(): r for r in records}

    target = by_platform.get(prefer)
    if target and target.get("sellPrice"):
        return target

    for name in (_cfg().get("preferred_platforms") or []):
        rec = by_platform.get(str(name).lower())
        if rec and rec.get("sellPrice"):
            return rec

    for rec in records:
        if rec.get("sellPrice"):
            return rec
    return records[0]


def _resolve_market_hash_name(item: dict) -> str | None:
    if item.get("market_hash_name"):
        return item["market_hash_name"]
    name = (item.get("name") or "").strip()
    if not name:
        return None
    return lookup_market_hash_name(name)


def _apply_price_update(
    connection,
    item: dict,
    new_price: float,
    platform: str,
    market_hash_name: str | None,
) -> dict:
    """更新一条 items：previous_price ← current_price；current_price ← new_price；重算利润。
    返回变更摘要 dict。"""
    now_str = now_local().strftime("%Y-%m-%d %H:%M:%S")
    old_price = float(item.get("current_price") or 0)
    sell_price = item.get("sell_price")
    sell_price_value = float(sell_price) if sell_price not in (None, "") else None

    fee_amount, profit, profit_rate = calculate_profit_fields(
        buy_price=float(item.get("buy_price") or 0),
        current_price=float(new_price),
        sell_price=sell_price_value,
        fee_rate=float(item.get("fee_rate") or 0.01),
        fee_amount=float(item.get("fee_amount") or 0),
        status=str(item.get("status") or "in_stock"),
    )

    connection.execute(
        """
        UPDATE items SET
            previous_price = current_price,
            current_price = ?,
            price_updated_at = ?,
            price_source = ?,
            market_hash_name = COALESCE(?, market_hash_name),
            fee_amount = ?,
            profit = ?,
            profit_rate = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            round(float(new_price), 2),
            now_str,
            platform,
            market_hash_name,
            fee_amount,
            profit,
            profit_rate,
            now_str,
            item["id"],
        ),
    )

    return {
        "id": item["id"],
        "name": item.get("name"),
        "previous_price": round(old_price, 2),
        "current_price": round(float(new_price), 2),
        "change": round(float(new_price) - old_price, 2),
        "platform": platform,
        "market_hash_name": market_hash_name or item.get("market_hash_name"),
        "price_updated_at": now_str,
    }


def _select_refreshable_items(connection, item_ids: list[int] | None) -> list[dict]:
    """默认只刷未售出的饰品。"""
    if item_ids:
        placeholders = ",".join(["?"] * len(item_ids))
        rows = connection.execute(
            f"SELECT * FROM items WHERE id IN ({placeholders})",
            tuple(item_ids),
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT * FROM items WHERE status <> 'sold'"
        ).fetchall()
    return [dict(r) for r in rows]


def refresh_prices(item_ids: list[int] | None = None, *, prefer_platform: str | None = None) -> dict[str, Any]:
    """批量刷价：按 market_hash_name 去重，调用 SteamDT price/batch（每分钟 1 次），
    缺失 mhn 的饰品尝试用 catalog 反查，再次缺失则跳过。"""
    cfg = _cfg()
    batch_size = int(cfg.get("price_batch_size") or 100)
    prefer = (prefer_platform or default_platform()).lower()

    with get_connection() as connection:
        items = _select_refreshable_items(connection, item_ids)
        if not items:
            return {"updated": 0, "skipped": 0, "details": []}

        resolved_mhn: dict[int, str] = {}
        skipped_no_name: list[dict] = []
        for it in items:
            mhn = _resolve_market_hash_name(it)
            if mhn:
                resolved_mhn[it["id"]] = mhn
            else:
                skipped_no_name.append({"id": it["id"], "name": it.get("name"), "reason": "no_market_hash_name"})

        mhn_to_items: dict[str, list[dict]] = {}
        for it in items:
            mhn = resolved_mhn.get(it["id"])
            if not mhn:
                continue
            mhn_to_items.setdefault(mhn, []).append(it)

        unique_mhns = list(mhn_to_items.keys())
        if not unique_mhns:
            return {
                "updated": 0,
                "skipped": len(skipped_no_name),
                "skipped_details": skipped_no_name,
                "details": [],
            }

        price_by_mhn: dict[str, dict] = {}
        for i in range(0, len(unique_mhns), batch_size):
            chunk = unique_mhns[i : i + batch_size]
            try:
                results = steamdt_service.query_price_batch(chunk)
            except steamdt_service.SteamDTError as exc:
                logger.warning(f"SteamDT price batch failed: {exc}")
                raise
            for item_group in results or []:
                mhn = item_group.get("marketHashName") or item_group.get("market_hash_name")
                if not mhn:
                    continue
                plats = item_group.get("dataList") or item_group.get("platforms") or item_group.get("data") or []
                picked = pick_price(plats, prefer=prefer)
                if picked and picked.get("sellPrice"):
                    price_by_mhn[mhn] = picked
            if i + batch_size < len(unique_mhns):
                # 批量接口 1 次/分钟
                time.sleep(62)

        details = []
        updated = 0
        skipped_no_price: list[dict] = []

        connection.execute("BEGIN")
        for mhn, group in mhn_to_items.items():
            picked = price_by_mhn.get(mhn)
            if not picked:
                for it in group:
                    skipped_no_price.append({"id": it["id"], "name": it.get("name"), "market_hash_name": mhn, "reason": "no_price"})
                continue
            platform = str(picked.get("platform") or prefer).lower()
            new_price = float(picked.get("sellPrice") or 0)
            for it in group:
                summary = _apply_price_update(connection, it, new_price, platform, mhn)
                details.append(summary)
                updated += 1
        connection.commit()

    skipped_total = len(skipped_no_name) + len(skipped_no_price)
    logger.info(
        f"Price refresh done: updated={updated}, skipped={skipped_total}"
        f" (no_name={len(skipped_no_name)}, no_price={len(skipped_no_price)})"
    )
    return {
        "updated": updated,
        "skipped": skipped_total,
        "skipped_details": skipped_no_name + skipped_no_price,
        "details": details,
    }


def refresh_price_for_item(item_id: int, *, prefer_platform: str | None = None) -> dict[str, Any]:
    """单条刷价：直接打 /price/single（60 次/分钟）。"""
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            return {"updated": 0, "error": "not_found"}
        item = dict(row)

    mhn = _resolve_market_hash_name(item)
    if not mhn:
        return {"updated": 0, "error": "no_market_hash_name"}

    records = steamdt_service.query_price(mhn)
    picked = pick_price(records, prefer=prefer_platform)
    if not picked or not picked.get("sellPrice"):
        return {"updated": 0, "error": "no_price", "market_hash_name": mhn}

    platform = str(picked.get("platform") or default_platform()).lower()
    new_price = float(picked.get("sellPrice") or 0)
    with get_connection() as connection:
        summary = _apply_price_update(connection, item, new_price, platform, mhn)
        connection.commit()
    return {"updated": 1, "item": summary}


def price_config() -> dict[str, Any]:
    cfg = _cfg()
    return {
        "default_platform": default_platform(),
        "preferred_platforms": [str(p).lower() for p in (cfg.get("preferred_platforms") or [])],
        "refresh_minutes": int(cfg.get("price_refresh_minutes") or 15),
    }
