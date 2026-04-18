from __future__ import annotations

import sqlite3

from app.core.config import DATABASE_PATH
from app.services.backup_service import backup_database_if_exists, ensure_storage_dirs


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    wear TEXT NOT NULL,
    steamdt_id TEXT,
    image_url TEXT NOT NULL,
    buy_price REAL NOT NULL,
    sell_price REAL,
    current_price REAL NOT NULL,
    fee_rate REAL NOT NULL DEFAULT 0.01,
    fee_amount REAL NOT NULL DEFAULT 0,
    profit REAL NOT NULL DEFAULT 0,
    profit_rate REAL NOT NULL DEFAULT 0,
    buy_platform TEXT,
    buy_time TEXT NOT NULL,
    sold_time TEXT,
    tradable_at TEXT,
    is_tradable INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'in_stock',
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
"""


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> str | None:
    ensure_storage_dirs()
    backup_path = backup_database_if_exists()
    with get_connection() as connection:
        connection.executescript(SCHEMA_SQL)
        _apply_migrations(connection)
        connection.commit()
    return backup_path


def _apply_migrations(connection: sqlite3.Connection) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(items)").fetchall()}
    if "sold_time" not in columns:
        connection.execute("ALTER TABLE items ADD COLUMN sold_time TEXT")
