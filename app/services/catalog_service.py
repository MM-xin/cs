from __future__ import annotations

import json
import re
from typing import Any

from app.core.database import get_connection
from app.core.item_logic import format_datetime, now_local
from app.core.logger import logger
from app.services import steamdt_service


WEAR_MAP_EN_TO_CN = {
    "Factory New": "崭新出厂",
    "Minimal Wear": "略有磨损",
    "Field-Tested": "久经沙场",
    "Well-Worn": "破损不堪",
    "Battle-Scarred": "战痕累累",
}

WEAR_MAP_CN_TO_EN = {v: k for k, v in WEAR_MAP_EN_TO_CN.items()}

WEAR_EN_PATTERN = re.compile(r"\s*\((Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)\)\s*$")
WEAR_CN_PATTERN = re.compile(r"\s*\((崭新出厂|略有磨损|久经沙场|破损不堪|战痕累累)\)\s*$")


def split_wear(name_cn: str, market_hash_name: str) -> tuple[str, str, str]:
    """返回 (base_name_cn, base_name_en, wear_cn)。"""
    wear_cn = ""

    m_en = WEAR_EN_PATTERN.search(market_hash_name or "")
    base_en = WEAR_EN_PATTERN.sub("", market_hash_name or "").strip()
    if m_en:
        wear_cn = WEAR_MAP_EN_TO_CN.get(m_en.group(1), "")

    m_cn = WEAR_CN_PATTERN.search(name_cn or "")
    base_cn = WEAR_CN_PATTERN.sub("", name_cn or "").strip()
    if m_cn and not wear_cn:
        wear_cn = m_cn.group(1)

    return base_cn, base_en, wear_cn


def _set_kv(connection, key: str, value: str) -> None:
    now = now_local().strftime("%Y-%m-%d %H:%M:%S")
    connection.execute(
        """
        INSERT INTO system_kv (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, value, now),
    )


def _get_kv(key: str) -> dict[str, str] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT key, value, updated_at FROM system_kv WHERE key = ?",
            (key,),
        ).fetchone()
    return dict(row) if row else None


def catalog_stats() -> dict[str, Any]:
    with get_connection() as connection:
        total = connection.execute("SELECT COUNT(1) AS c FROM item_catalog").fetchone()["c"]
        last_updated_row = connection.execute(
            "SELECT MAX(updated_at) AS latest FROM item_catalog"
        ).fetchone()
    last_sync = _get_kv("catalog.last_sync") or {}
    return {
        "total": int(total or 0),
        "latest_row_updated_at": format_datetime(last_updated_row["latest"]) if last_updated_row and last_updated_row["latest"] else None,
        "last_sync_at": format_datetime(last_sync.get("updated_at")) if last_sync else None,
        "last_sync_status": last_sync.get("value") if last_sync else None,
    }


def sync_catalog_from_steamdt() -> dict[str, Any]:
    """调用 SteamDT /base 拉全量目录并落库。接口限频：每日 1 次。"""
    logger.info("Catalog sync starting (SteamDT /base)")
    data = steamdt_service.fetch_base_info()
    if not isinstance(data, list):
        raise steamdt_service.SteamDTError("SteamDT /base 返回格式异常")

    now_str = now_local().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0
    updated = 0

    with get_connection() as connection:
        existing = {
            row["market_hash_name"]
            for row in connection.execute("SELECT market_hash_name FROM item_catalog").fetchall()
        }
        connection.execute("BEGIN")
        for item in data:
            market_hash_name = (item.get("marketHashName") or "").strip()
            name_cn = (item.get("name") or "").strip()
            if not market_hash_name:
                continue
            base_cn, base_en, wear_cn = split_wear(name_cn, market_hash_name)
            platform_list = item.get("platformList") or []
            platform_list_json = json.dumps(platform_list, ensure_ascii=False)

            if market_hash_name in existing:
                updated += 1
            else:
                inserted += 1

            connection.execute(
                """
                INSERT INTO item_catalog (
                    market_hash_name, name_cn, base_name_cn, base_name_en, wear, platform_list, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_hash_name) DO UPDATE SET
                    name_cn = excluded.name_cn,
                    base_name_cn = excluded.base_name_cn,
                    base_name_en = excluded.base_name_en,
                    wear = excluded.wear,
                    platform_list = excluded.platform_list,
                    updated_at = excluded.updated_at
                """,
                (market_hash_name, name_cn, base_cn, base_en, wear_cn, platform_list_json, now_str),
            )
        _set_kv(connection, "catalog.last_sync", f"ok (inserted={inserted}, updated={updated})")
        connection.commit()

    total_now = inserted + updated
    logger.info(f"Catalog sync done: total_records_in_payload={total_now}, inserted={inserted}, updated={updated}")
    return {
        "inserted": inserted,
        "updated": updated,
        "total_in_payload": total_now,
        "synced_at": now_str,
    }


def search_catalog(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """保留旧签名，默认只取前 N 条（供 autocomplete 等场景使用）。"""
    result = search_catalog_paginated(query, page=1, size=limit)
    return result["items"]


ALLOWED_PAGE_SIZES = {10, 20, 50, 100, 200}


def search_catalog_paginated(
    query: str,
    *,
    page: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    """分页搜索。query 为空时返回全表分页（便于左侧目录浏览）。"""
    query = (query or "").strip()
    if size not in ALLOWED_PAGE_SIZES:
        size = 20
    page = max(1, int(page or 1))
    offset = (page - 1) * size

    with get_connection() as connection:
        if query:
            pattern = f"%{query}%"
            total_row = connection.execute(
                """
                SELECT COUNT(1) AS c FROM item_catalog
                WHERE name_cn LIKE ?
                   OR base_name_cn LIKE ?
                   OR base_name_en LIKE ?
                   OR market_hash_name LIKE ?
                """,
                (pattern, pattern, pattern, pattern),
            ).fetchone()
            rows = connection.execute(
                """
                SELECT market_hash_name, name_cn, base_name_cn, base_name_en, wear
                FROM item_catalog
                WHERE name_cn LIKE ?
                   OR base_name_cn LIKE ?
                   OR base_name_en LIKE ?
                   OR market_hash_name LIKE ?
                ORDER BY
                    CASE
                        WHEN name_cn = ? THEN 0
                        WHEN market_hash_name = ? THEN 0
                        WHEN base_name_cn = ? THEN 1
                        WHEN base_name_en = ? THEN 1
                        ELSE 2
                    END,
                    LENGTH(name_cn),
                    name_cn
                LIMIT ? OFFSET ?
                """,
                (pattern, pattern, pattern, pattern, query, query, query, query, size, offset),
            ).fetchall()
        else:
            total_row = connection.execute("SELECT COUNT(1) AS c FROM item_catalog").fetchone()
            rows = connection.execute(
                """
                SELECT market_hash_name, name_cn, base_name_cn, base_name_en, wear
                FROM item_catalog
                ORDER BY name_cn
                LIMIT ? OFFSET ?
                """,
                (size, offset),
            ).fetchall()

    total = int(total_row["c"] or 0) if total_row else 0
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "size": size,
    }


def lookup_market_hash_name(name_cn_full: str) -> str | None:
    """精确匹配中文全名（含磨损括号）→ marketHashName。"""
    if not name_cn_full:
        return None
    with get_connection() as connection:
        row = connection.execute(
            "SELECT market_hash_name FROM item_catalog WHERE name_cn = ? LIMIT 1",
            (name_cn_full,),
        ).fetchone()
    return row["market_hash_name"] if row else None
