from __future__ import annotations

from datetime import datetime
from shutil import copy2

from app.core.config import BACKUP_DIR, BACKUP_RETENTION, DATABASE_PATH, DATA_DIR


def ensure_storage_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def backup_database_if_exists() -> str | None:
    ensure_storage_dirs()
    if not DATABASE_PATH.exists() or DATABASE_PATH.stat().st_size == 0:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"items_{timestamp}.db"
    copy2(DATABASE_PATH, backup_path)
    cleanup_old_backups()
    return str(backup_path)


def cleanup_old_backups() -> None:
    backups = sorted(BACKUP_DIR.glob("items_*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
    for old_backup in backups[BACKUP_RETENTION:]:
        old_backup.unlink(missing_ok=True)
