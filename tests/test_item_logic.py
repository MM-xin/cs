from __future__ import annotations

from datetime import datetime

from app.core.item_logic import (
    calculate_fee_amount,
    calculate_is_tradable,
    calculate_profit_fields,
    calculate_remaining_time,
    calculate_tradable_at,
    parse_datetime,
)


class TestTradableLogic:
    def test_tradable_at_before_16(self):
        # 09:00 购买 -> 当日 16:00 + 7 天 = 第8天 16:00
        result = calculate_tradable_at("2026-01-01 09:00:00")
        assert result == "2026-01-08 16:00:00"

    def test_tradable_at_after_16(self):
        # 17:00 购买 -> 次日 16:00 + 7 天 = 第9天 16:00
        result = calculate_tradable_at("2026-01-01 17:00:00")
        assert result == "2026-01-09 16:00:00"

    def test_tradable_at_exactly_16(self):
        # 16:00 当作 "已到 16:00" 处理
        result = calculate_tradable_at("2026-01-01 16:00:00")
        assert result == "2026-01-09 16:00:00"

    def test_tradable_at_invalid(self):
        assert calculate_tradable_at("") is None
        assert calculate_tradable_at(None) is None
        assert calculate_tradable_at("bad") is None

    def test_is_tradable_reached(self):
        now = datetime(2026, 1, 10, 17, 0, 0)
        assert calculate_is_tradable("2026-01-09 16:00:00", now) is True

    def test_is_tradable_not_reached(self):
        now = datetime(2026, 1, 5, 10, 0, 0)
        assert calculate_is_tradable("2026-01-09 16:00:00", now) is False

    def test_is_tradable_empty(self):
        assert calculate_is_tradable(None) is True
        assert calculate_is_tradable("") is True

    def test_remaining_time_done(self):
        now = datetime(2026, 1, 10, 0, 0, 0)
        assert calculate_remaining_time("2026-01-01 00:00:00", now) == "-"

    def test_remaining_time_days(self):
        now = datetime(2026, 1, 1, 16, 0, 0)
        remaining = calculate_remaining_time("2026-01-09 16:00:00", now)
        assert "天" in remaining and "8" in remaining


class TestFeeCalc:
    def test_fee_from_rate(self):
        assert calculate_fee_amount(100.0, 0.01) == 1.0

    def test_fee_overridden(self):
        assert calculate_fee_amount(100.0, 0.01, 3.0) == 3.0

    def test_fee_no_sell(self):
        assert calculate_fee_amount(None, 0.01) == 0.0

    def test_fee_rounding(self):
        assert calculate_fee_amount(33.333, 0.01) == 0.33


class TestProfitFields:
    def test_profit_sold(self):
        fee, profit, rate = calculate_profit_fields(
            buy_price=100.0,
            current_price=120.0,
            sell_price=150.0,
            fee_rate=0.01,
            fee_amount=None,
            status="sold",
        )
        assert fee == 1.5
        assert profit == 48.5
        assert rate == round(48.5 / 100.0, 4)

    def test_profit_in_stock_uses_current_price(self):
        fee, profit, rate = calculate_profit_fields(
            buy_price=100.0,
            current_price=130.0,
            sell_price=None,
            fee_rate=0.01,
            fee_amount=None,
            status="in_stock",
        )
        assert fee == 0.0
        assert profit == 30.0
        assert rate == 0.3

    def test_profit_withdrawn(self):
        fee, profit, rate = calculate_profit_fields(
            buy_price=100.0,
            current_price=110.0,
            sell_price=95.0,
            fee_rate=0.01,
            fee_amount=2.0,
            status="withdrawn",
        )
        assert fee == 2.0
        assert profit == -7.0
        assert rate == round(-7.0 / 100.0, 4)

    def test_profit_zero_buy(self):
        fee, profit, rate = calculate_profit_fields(
            buy_price=0.0,
            current_price=10.0,
            sell_price=None,
            fee_rate=0.01,
            fee_amount=None,
            status="in_stock",
        )
        assert rate == 0.0
        assert profit == 10.0


class TestParse:
    def test_parse_full(self):
        assert parse_datetime("2026-01-02 03:04:05") == datetime(2026, 1, 2, 3, 4, 5)

    def test_parse_form(self):
        assert parse_datetime("2026-01-02T03:04") == datetime(2026, 1, 2, 3, 4, 0)

    def test_parse_invalid(self):
        assert parse_datetime("xxx") is None
        assert parse_datetime("") is None
