"""In-process APScheduler wiring for the daily report.

A module-level flag prevents a double-start if the app factory runs twice.
Jobs are idempotent; a cron entry in deploy.sh is the durability safety net.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_started = False


def start_scheduler(report_service) -> None:
    """Start the background scheduler with a daily report job (once)."""
    global _started
    if _started:
        return

    hour = int(os.environ.get("REPORT_HOUR", "8"))
    minute = int(os.environ.get("REPORT_MINUTE", "0"))

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning("APScheduler not installed; daily report disabled.")
        return

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        report_service.send,
        "cron",
        hour=hour,
        minute=minute,
        id="daily_report",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    _started = True
    logger.info("Scheduler started: daily report at %02d:%02d local", hour, minute)
