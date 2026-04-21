from __future__ import annotations

import json
from typing import Any

from app.core.database import get_connection
from app.core.item_logic import format_datetime, now_local
from app.core.logger import logger


AUDIT_ACTIONS = {
    "item.create": "创建饰品",
    "item.create.bulk": "批量新增",
    "item.update": "编辑饰品",
    "item.inline_update": "行内修改",
    "item.delete": "删除饰品",
    "item.clone": "复制饰品",
    "item.sell.bulk": "批量出售",
    "item.recalculate": "重算利润",
    "trade.manual": "手动流水",
    "backup.manual": "手动备份",
    "backup.scheduled": "定时备份",
    "catalog.sync.manual": "手动同步饰品目录",
    "catalog.sync.scheduled": "定时同步饰品目录",
    "price.refresh.manual": "手动刷价",
    "price.refresh.single": "单条刷价",
    "price.refresh.scheduled": "定时刷价",
}


def _dumps(payload: Any) -> str | None:
    if payload is None:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return json.dumps(str(payload), ensure_ascii=False)


def record_audit(
    *,
    action: str,
    username: str = "system",
    item_id: int | None = None,
    detail: Any = None,
    success: bool = True,
) -> None:
    created_at = now_local().strftime("%Y-%m-%d %H:%M:%S")
    detail_json = _dumps(detail)
    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO audit_logs (
                    action, username, item_id, detail, success, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (action, username, item_id, detail_json, 1 if success else 0, created_at),
            )
            connection.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to write audit log: action={action}, err={exc}")

    log_level = "info" if success else "warning"
    label = AUDIT_ACTIONS.get(action, action)
    getattr(logger, log_level)(
        f"audit | user={username} | action={action}({label}) | item_id={item_id} | success={success}"
    )


def list_audit_logs(limit: int = 200) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        entry = dict(row)
        entry["created_at_display"] = format_datetime(entry.get("created_at"))
        entry["action_label"] = AUDIT_ACTIONS.get(entry.get("action"), entry.get("action"))
        detail_raw = entry.get("detail")
        if detail_raw:
            try:
                entry["detail"] = json.loads(detail_raw)
            except (TypeError, ValueError):
                pass
        entry["success"] = bool(entry.get("success"))
        result.append(entry)
    return result
