from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.logger import logger
from app.services.audit_service import record_audit
from app.services.backup_service import backup_database_if_exists
from app.services.catalog_service import sync_catalog_from_steamdt
from app.services.price_service import price_config, refresh_prices


_scheduler: BackgroundScheduler | None = None


def _do_scheduled_backup() -> None:
    try:
        backup_path = backup_database_if_exists()
        record_audit(
            action="backup.scheduled",
            username="scheduler",
            detail={"backup_path": backup_path},
            success=backup_path is not None,
        )
        if backup_path:
            logger.info(f"scheduled backup ok: {backup_path}")
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"scheduled backup failed: {exc}")
        record_audit(
            action="backup.scheduled",
            username="scheduler",
            detail={"error": str(exc)},
            success=False,
        )


def _do_scheduled_catalog_sync() -> None:
    try:
        result = sync_catalog_from_steamdt()
        record_audit(
            action="catalog.sync.scheduled",
            username="scheduler",
            detail=result,
            success=True,
        )
        logger.info(f"scheduled catalog sync ok: {result}")
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"scheduled catalog sync failed: {exc}")
        record_audit(
            action="catalog.sync.scheduled",
            username="scheduler",
            detail={"error": str(exc)},
            success=False,
        )


def _do_scheduled_price_refresh() -> None:
    try:
        result = refresh_prices()
        record_audit(
            action="price.refresh.scheduled",
            username="scheduler",
            detail={"updated": result.get("updated"), "skipped": result.get("skipped")},
            success=True,
        )
        logger.info(
            f"scheduled price refresh ok: updated={result.get('updated')}, skipped={result.get('skipped')}"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"scheduled price refresh failed: {exc}")
        record_audit(
            action="price.refresh.scheduled",
            username="scheduler",
            detail={"error": str(exc)},
            success=False,
        )


def start_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        _do_scheduled_backup,
        "cron",
        hour=4,
        minute=0,
        id="daily_backup",
        replace_existing=True,
    )
    scheduler.add_job(
        _do_scheduled_catalog_sync,
        "cron",
        hour=5,
        minute=0,
        id="daily_catalog_sync",
        replace_existing=True,
    )
    interval = int(price_config().get("refresh_minutes") or 15)
    scheduler.add_job(
        _do_scheduled_price_refresh,
        "interval",
        minutes=interval,
        id="price_refresh",
        replace_existing=True,
        next_run_time=None,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "APScheduler started: daily_backup @ 04:00, daily_catalog_sync @ 05:00, "
        f"price_refresh every {interval}min"
    )


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler shutdown")
        _scheduler = None
