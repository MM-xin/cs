from __future__ import annotations

from typing import Any

import httpx

from app.core.config import load_steamdt_config
from app.core.logger import logger


class SteamDTError(RuntimeError):
    """SteamDT 接口调用失败时抛出。"""

    def __init__(self, message: str, *, error_code: int | str | None = None, payload: Any = None):
        super().__init__(message)
        self.error_code = error_code
        self.payload = payload


def _config() -> dict:
    cfg = load_steamdt_config()
    if not cfg.get("api_key"):
        raise SteamDTError("SteamDT 未配置 api_key，请在 config/steamdt.yaml 中设置")
    return cfg


def _client() -> httpx.Client:
    cfg = _config()
    return httpx.Client(
        base_url=cfg.get("base_url") or "https://open.steamdt.com",
        headers={
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=float(cfg.get("timeout_seconds") or 15),
    )


def _parse_response(resp: httpx.Response) -> Any:
    if resp.status_code != 200:
        raise SteamDTError(
            f"HTTP {resp.status_code}: {resp.text[:200]}",
            error_code=resp.status_code,
            payload=resp.text,
        )
    data = resp.json()
    if not data.get("success"):
        raise SteamDTError(
            data.get("errorMsg") or "SteamDT 未知错误",
            error_code=data.get("errorCode") or data.get("errorCodeStr"),
            payload=data,
        )
    return data.get("data")


def ping() -> dict:
    """用 single 价格接口探测连通性（有效 key 必返 success=true）。"""
    sample_name = "AK-47 | Redline (Field-Tested)"
    with _client() as client:
        resp = client.get("/open/cs2/v1/price/single", params={"marketHashName": sample_name})
        data = _parse_response(resp)
    logger.info(f"SteamDT ping ok, sample={sample_name}, platforms={len(data or [])}")
    return {
        "market_hash_name": sample_name,
        "platform_count": len(data or []),
        "sample": (data or [])[:3],
    }


def query_price(market_hash_name: str) -> list[dict]:
    """查询单个饰品在各平台的在售/求购价格。"""
    if not market_hash_name:
        raise SteamDTError("marketHashName 不能为空")
    with _client() as client:
        resp = client.get(
            "/open/cs2/v1/price/single",
            params={"marketHashName": market_hash_name},
        )
        data = _parse_response(resp)
    return data or []


def fetch_base_info() -> list[dict]:
    """获取全量饰品基础信息（中文名↔marketHashName↔各平台 itemId）。
    官方限频：每日 1 次，必须本地缓存。"""
    cfg = _config()
    timeout = float(cfg.get("timeout_seconds") or 60)
    # /base 返回数据量较大，单独给更长超时
    with httpx.Client(
        base_url=cfg.get("base_url") or "https://open.steamdt.com",
        headers={
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=max(timeout, 60),
    ) as client:
        resp = client.get("/open/cs2/v1/base")
        data = _parse_response(resp)
    return data or []


def query_price_batch(names: list[str]) -> list[dict]:
    """批量查询价格（上限 100，接口限频每分钟 1 次）。"""
    if not names:
        return []
    if len(names) > 100:
        raise SteamDTError("批量查询最多 100 个 marketHashName")
    with _client() as client:
        resp = client.post(
            "/open/cs2/v1/price/batch",
            json={"marketHashNames": names},
        )
        data = _parse_response(resp)
    return data or []


def pick_preferred_price(records: list[dict]) -> dict | None:
    """按配置中的 preferred_platforms 顺序挑选第一个有效 sellPrice。"""
    cfg = _config()
    preferred = [p.lower() for p in (cfg.get("preferred_platforms") or [])]
    if not records:
        return None
    by_platform = {str(r.get("platform") or "").lower(): r for r in records}
    for platform in preferred:
        rec = by_platform.get(platform)
        if rec and rec.get("sellPrice"):
            return rec
    for rec in records:
        if rec.get("sellPrice"):
            return rec
    return records[0]
