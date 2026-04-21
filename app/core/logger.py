from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.core.config import PROJECT_ROOT


LOG_DIR = PROJECT_ROOT / "logs"


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <7}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        ),
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )
    logger.add(
        LOG_DIR / "app_{time:YYYY-MM-DD}.log",
        level="INFO",
        rotation="00:00",
        retention="14 days",
        encoding="utf-8",
        enqueue=True,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {name}:{line} - {message}",
    )
    logger.add(
        LOG_DIR / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {name}:{line} - {message}",
    )


def get_logger():
    return logger


__all__ = ["setup_logging", "get_logger", "logger", "LOG_DIR"]
