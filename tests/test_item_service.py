from __future__ import annotations

import pytest


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    """给每个测试提供一个独立的临时数据库，避免污染生产数据。"""
    from app.core import config as config_module
    from app.core import database as database_module

    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    data_dir.mkdir()
    backup_dir.mkdir()
    db_path = data_dir / "test_items.db"

    monkeypatch.setattr(config_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(config_module, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(config_module, "DATABASE_PATH", db_path)
    monkeypatch.setattr(database_module, "DATABASE_PATH", db_path)

    from app.services import backup_service as backup_module

    monkeypatch.setattr(backup_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(backup_module, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(backup_module, "DATABASE_PATH", db_path)

    database_module.initialize_database()
    yield


class TestItemService:
    def test_create_and_get_item(self, isolated_db):
        from app.services.item_service import create_item, get_item

        item_id = create_item(
            {
                "name": "AK-47 | Redline",
                "category": "步枪",
                "wear": "久经沙场",
                "buy_price": "100",
                "buy_time": "2026-01-01 10:00:00",
            }
        )
        item = get_item(item_id)
        assert item is not None
        assert item["name"] == "AK-47 | Redline"
        assert item["buy_price"] == 100.0
        assert item["status"] == "in_stock"

    def test_inline_update_sell_price_marks_sold(self, isolated_db):
        from app.services.item_service import (
            create_item,
            get_item,
            inline_update_item,
        )

        item_id = create_item(
            {
                "name": "Test",
                "category": "步枪",
                "wear": "崭新出厂",
                "buy_price": "100",
                "buy_time": "2020-01-01 10:00:00",
            }
        )
        ok = inline_update_item(item_id, "sell_price", "200")
        assert ok is True
        item = get_item(item_id)
        assert item["status"] == "sold"
        assert item["sell_price"] == 200.0
        assert item["fee_amount"] == 2.0
        assert item["profit"] == 98.0
        assert item["sold_time"] is not None

    def test_inline_clear_sell_price_back_to_in_stock(self, isolated_db):
        from app.services.item_service import (
            create_item,
            get_item,
            inline_update_item,
        )

        item_id = create_item(
            {
                "name": "Test",
                "category": "步枪",
                "wear": "崭新出厂",
                "buy_price": "100",
                "sell_price": "150",
                "buy_time": "2020-01-01 10:00:00",
            }
        )
        inline_update_item(item_id, "sell_price", "")
        item = get_item(item_id)
        assert item["sell_price"] is None
        assert item["status"] == "in_stock"
        assert item["sold_time"] is None

    def test_dashboard_summary(self, isolated_db):
        from app.services.item_service import create_item, dashboard_summary, update_item

        create_item(
            {
                "name": "A",
                "category": "步枪",
                "wear": "崭新出厂",
                "buy_price": "100",
                "buy_time": "2020-01-01 10:00:00",
            }
        )
        sold_id = create_item(
            {
                "name": "B",
                "category": "步枪",
                "wear": "崭新出厂",
                "buy_price": "100",
                "sell_price": "200",
                "buy_time": "2020-01-01 10:00:00",
            }
        )
        summary = dashboard_summary()
        assert summary["counts"]["total"] == 2
        assert summary["counts"]["in_stock"] == 1
        assert summary["counts"]["sold"] == 1
        assert summary["realized"]["profit"] == 98.0

    def test_recalculate_all(self, isolated_db):
        from app.core.database import get_connection
        from app.services.item_service import create_item, get_item, recalculate_all

        item_id = create_item(
            {
                "name": "C",
                "category": "步枪",
                "wear": "崭新出厂",
                "buy_price": "100",
                "sell_price": "150",
                "buy_time": "2020-01-01 10:00:00",
            }
        )
        with get_connection() as conn:
            conn.execute("UPDATE items SET profit = 0, fee_amount = 0 WHERE id = ?", (item_id,))
            conn.commit()
        result = recalculate_all()
        assert result["updated"] >= 1
        item = get_item(item_id)
        assert item["fee_amount"] == 1.5
        assert item["profit"] == 48.5

    def test_export_csv(self, isolated_db):
        from app.services.item_service import create_item, export_items_csv

        create_item(
            {
                "name": "Export Test",
                "category": "步枪",
                "wear": "崭新出厂",
                "buy_price": "100",
                "buy_time": "2020-01-01 10:00:00",
            }
        )
        csv_text = export_items_csv({})
        assert "Export Test" in csv_text
        assert "名称" in csv_text
