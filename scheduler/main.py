"""
The scheduler. Run this and leave it running (in its own terminal, or as a
background task) -- it repeats the discovery cycle, email tracking, health
checks, and daily report automatically, on the intervals set in
config/settings.yaml.

Usage: python -m scheduler.main
Stop with Ctrl+C.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.config_loader import load_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/agent.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def parse_schedule_config(settings: dict) -> dict:
    """Pure function: turns settings.yaml's schedule section into the
    plain values the scheduler needs. Kept separate from build_scheduler()
    (which requires the apscheduler library) so this parsing/validation
    logic is testable without that dependency installed."""
    schedule_cfg = settings.get("schedule", {})

    daily_report_time = schedule_cfg.get("daily_report_time", "21:00")
    try:
        report_hour, report_minute = (int(x) for x in daily_report_time.split(":"))
    except (ValueError, AttributeError):
        logger.warning(
            "Invalid daily_report_time '%s' in settings.yaml, falling back to 21:00",
            daily_report_time,
        )
        report_hour, report_minute = 21, 0

    return {
        "discovery_hours": schedule_cfg.get("job_discovery_interval_hours", 3),
        "email_minutes": schedule_cfg.get("email_tracking_interval_minutes", 30),
        "health_minutes": schedule_cfg.get("health_check_interval_minutes", 15),
        "report_hour": report_hour,
        "report_minute": report_minute,
    }


def build_scheduler():
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from scheduler.jobs import discovery_job, email_tracking_job, daily_report_job, health_check_job

    settings = load_settings()
    cfg = parse_schedule_config(settings)

    scheduler = BlockingScheduler()

    scheduler.add_job(
        discovery_job, "interval", hours=cfg["discovery_hours"],
        id="discovery", misfire_grace_time=600,
    )
    scheduler.add_job(
        email_tracking_job, "interval", minutes=cfg["email_minutes"],
        id="email_tracking", misfire_grace_time=300,
    )
    scheduler.add_job(
        health_check_job, "interval", minutes=cfg["health_minutes"],
        id="health_check", misfire_grace_time=120,
    )
    scheduler.add_job(
        daily_report_job, CronTrigger(hour=cfg["report_hour"], minute=cfg["report_minute"]),
        id="daily_report",
    )

    return scheduler


def main() -> None:
    from scheduler.jobs import discovery_job

    logger.info("Starting scheduler. Running an initial discovery cycle now...")
    discovery_job()  # run once immediately on startup, don't wait for the first interval

    scheduler = build_scheduler()
    logger.info("Scheduler started. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
