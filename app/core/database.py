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

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    trade_type TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    fee_amount REAL NOT NULL DEFAULT 0,
    net_amount REAL NOT NULL DEFAULT 0,
    trade_time TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'system',
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_item_id ON trades(item_id);
CREATE INDEX IF NOT EXISTS idx_trades_trade_time ON trades(trade_time);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    username TEXT NOT NULL DEFAULT 'system',
    item_id INTEGER,
    detail TEXT,
    success INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);

CREATE TABLE IF NOT EXISTS item_catalog (
    market_hash_name TEXT PRIMARY KEY,
    name_cn TEXT NOT NULL,
    base_name_cn TEXT,
    base_name_en TEXT,
    wear TEXT,
    platform_list TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_item_catalog_name_cn ON item_catalog(name_cn);
CREATE INDEX IF NOT EXISTS idx_item_catalog_base_name_cn ON item_catalog(base_name_cn);
CREATE INDEX IF NOT EXISTS idx_item_catalog_base_name_en ON item_catalog(base_name_en);

CREATE TABLE IF NOT EXISTS system_kv (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT NOT NULL
);
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
    if "market_hash_name" not in columns:
        connection.execute("ALTER TABLE items ADD COLUMN market_hash_name TEXT")
    if "previous_price" not in columns:
        connection.execute("ALTER TABLE items ADD COLUMN previous_price REAL")
    if "price_updated_at" not in columns:
        connection.execute("ALTER TABLE items ADD COLUMN price_updated_at TEXT")
    if "price_source" not in columns:
        connection.execute("ALTER TABLE items ADD COLUMN price_source TEXT")

    trade_columns = {row["name"] for row in connection.execute("PRAGMA table_info(trades)").fetchall()}
    if not trade_columns:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                trade_type TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                fee_amount REAL NOT NULL DEFAULT 0,
                net_amount REAL NOT NULL DEFAULT 0,
                trade_time TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'system',
                note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_trades_item_id ON trades(item_id);
            CREATE INDEX IF NOT EXISTS idx_trades_trade_time ON trades(trade_time);
            """
        )

    catalog_columns = {row["name"] for row in connection.execute("PRAGMA table_info(item_catalog)").fetchall()}
    if not catalog_columns:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS item_catalog (
                market_hash_name TEXT PRIMARY KEY,
                name_cn TEXT NOT NULL,
                base_name_cn TEXT,
                base_name_en TEXT,
                wear TEXT,
                platform_list TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_item_catalog_name_cn ON item_catalog(name_cn);
            CREATE INDEX IF NOT EXISTS idx_item_catalog_base_name_cn ON item_catalog(base_name_cn);
            CREATE INDEX IF NOT EXISTS idx_item_catalog_base_name_en ON item_catalog(base_name_en);
            """
        )

    kv_columns = {row["name"] for row in connection.execute("PRAGMA table_info(system_kv)").fetchall()}
    if not kv_columns:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS system_kv (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT NOT NULL
            );
            """
        )

    audit_columns = {row["name"] for row in connection.execute("PRAGMA table_info(audit_logs)").fetchall()}
    if not audit_columns:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                username TEXT NOT NULL DEFAULT 'system',
                item_id INTEGER,
                detail TEXT,
                success INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
            CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
            """
        )
