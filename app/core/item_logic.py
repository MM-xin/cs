from __future__ import annotations

from datetime import datetime, timedelta


DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
FORM_DATETIME_FORMAT = "%Y-%m-%dT%H:%M"


def now_local() -> datetime:
    return datetime.now().replace(microsecond=0)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    for fmt in (DATETIME_FORMAT, FORM_DATETIME_FORMAT):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def format_datetime(value: str | None) -> str:
    parsed = parse_datetime(value)
    if not parsed:
        return ""
    return parsed.strftime(DATETIME_FORMAT)


def format_form_datetime(value: str | None) -> str:
    parsed = parse_datetime(value)
    if not parsed:
        return ""
    return parsed.strftime(FORM_DATETIME_FORMAT)


def calculate_tradable_at(buy_time: str | None) -> str | None:
    buy_dt = parse_datetime(buy_time)
    if not buy_dt:
        return None

    next_sixteen = buy_dt.replace(hour=16, minute=0, second=0, microsecond=0)
    if buy_dt >= next_sixteen:
        next_sixteen += timedelta(days=1)

    tradable_at = next_sixteen + timedelta(days=7)
    return tradable_at.strftime(DATETIME_FORMAT)


def calculate_is_tradable(tradable_at: str | None, current_time: datetime | None = None) -> bool:
    tradable_dt = parse_datetime(tradable_at)
    if not tradable_dt:
        return True
    current_dt = current_time or now_local()
    return current_dt >= tradable_dt


def calculate_remaining_time(tradable_at: str | None, current_time: datetime | None = None) -> str:
    tradable_dt = parse_datetime(tradable_at)
    if not tradable_dt:
        return "-"
    current_dt = current_time or now_local()
    if current_dt >= tradable_dt:
        return "-"
    
    diff = tradable_dt - current_dt
    days = diff.days
    hours, remainder = divmod(diff.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}天 {hours}时 {minutes}分"
    if hours > 0:
        return f"{hours}时 {minutes}分"
    return f"{minutes}分"


def calculate_fee_amount(
    sell_price: float | None,
    fee_rate: float,
    provided_fee_amount: float | None = None,
) -> float:
    if provided_fee_amount is not None:
        return round(provided_fee_amount, 2)
    if sell_price is None:
        return 0.0
    return round(sell_price * fee_rate, 2)


def calculate_profit_fields(
    *,
    buy_price: float,
    current_price: float,
    sell_price: float | None,
    fee_rate: float,
    fee_amount: float | None,
    status: str,
) -> tuple[float, float, float]:
    if status == "sold":
        resolved_sell_price = sell_price or 0.0
        resolved_fee_amount = round(resolved_sell_price * fee_rate, 2)
        profit = resolved_sell_price - buy_price - resolved_fee_amount
    elif status == "withdrawn":
        resolved_fee_amount = round(fee_amount or 0.0, 2)
        resolved_sell_price = sell_price or 0.0
        profit = resolved_sell_price - buy_price - resolved_fee_amount
    else:
        profit = current_price - buy_price
        resolved_fee_amount = 0.0

    profit_rate = profit / buy_price if buy_price else 0.0
    return round(resolved_fee_amount, 2), round(profit, 2), round(profit_rate, 4)
