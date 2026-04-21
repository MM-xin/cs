from __future__ import annotations

from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
USERS_CONFIG_PATH = PROJECT_ROOT / "config" / "users.yaml"
STEAMDT_CONFIG_PATH = PROJECT_ROOT / "config" / "steamdt.yaml"
DATA_DIR = PROJECT_ROOT / "data"
BACKUP_DIR = PROJECT_ROOT / "backups"
DATABASE_PATH = DATA_DIR / "items.db"

DEFAULT_IMAGE_URL = "https://placehold.co/120x90?text=CS2"
DEFAULT_FEE_RATE = 0.01
BACKUP_RETENTION = 7


def load_steamdt_config() -> dict:
    """读取 SteamDT 配置；文件不存在则返回空配置，由调用方决定是否报错。"""
    if not STEAMDT_CONFIG_PATH.exists():
        return {}
    with STEAMDT_CONFIG_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return data.get("steamdt", {}) or {}


def load_user_credentials() -> dict[str, str]:
    if not USERS_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing user config file: {USERS_CONFIG_PATH}")

    with USERS_CONFIG_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    users = data.get("users", [])
    credentials = {
        str(user.get("username", "")).strip(): str(user.get("password", ""))
        for user in users
        if user.get("username")
    }

    if not credentials:
        raise ValueError("No valid users found in users config file.")

    return credentials
