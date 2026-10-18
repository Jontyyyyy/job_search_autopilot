"""
The actual tasks the scheduler runs on a timer. Each function is written to
never raise -- a failure in one task (a provider outage, a bad network
request) is logged and swallowed so the scheduler itself keeps running
every other task on schedule, rather than one bad run taking the whole
agent down.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3

from database.schema import init_db
from database.repository import save_email, get_today_stats
from agent.pipeline import run_discovery_cycle
from email_tracking.gmail_client import GmailClient
from email_tracking.classifier import classify_email
from notifications.telegram_bot import TelegramNotifier
from notifications.message_formatting import (
    format_job_match_alert, format_shortlist_alert, format_daily_summary,
    format_health_check_failure,
)
from utils.config_loader import load_profile, load_companies, load_settings

logger = logging.getLogger(__name__)

# High-priority classifications that justify an immediate Telegram ping,
# rather than waiting for the daily summary.
URGENT_CLASSIFICATIONS = {"shortlisted", "interview", "assessment"}


def _get_conn() -> sqlite3.Connection:
    settings = load_settings()
    db_path = settings.get("database", {}).get("path", "data/job_autopilot.db")
    return init_db(db_path)


def discovery_job() -> None:
    """Runs the discover -> score -> tailor cycle, and pings Telegram for
    any newly discovered strong match."""
    try:
        profile = load_profile()
        companies = load_companies()
        conn = _get_conn()
        stats = run_discovery_cycle(conn, profile, companies)
        conn.close()

        notifier = TelegramNotifier()
        for job, score in stats["strong_matches"]:
            from ai.matcher import score_job
            match = score_job(job, profile)  # rebuild for the full reasoning text
            text = format_job_match_alert(job, match)
            asyncio.run(notifier.send(text))

        logger.info(
            "Discovery cycle: discovered=%d new=%d scored=%d resumes=%d",
            stats["jobs_discovered"], stats["jobs_new"], stats["jobs_scored"],
            stats["resumes_generated"],
        )
    except Exception as exc:
        logger.error("Discovery job failed: %s", exc)
        _notify_health_failure("Discovery", str(exc))


def email_tracking_job() -> None:
    """Checks Gmail for new emails, classifies them, saves them, and alerts
    immediately on anything urgent (shortlist, interview, assessment)."""
    try:
        gmail = GmailClient()
        if not gmail.is_configured:
            logger.info("Gmail not configured yet -- skipping email tracking.")
            return

        conn = _get_conn()
        notifier = TelegramNotifier()
        emails = gmail.fetch_recent_emails(since_days=1, limit=50)

        for email in emails:
            classification = classify_email(email.subject, email.body)
            save_email(conn, email, classification, job_id=None)

            if classification.category in URGENT_CLASSIFICATIONS and classification.confidence >= 0.6:
                from discovery.job_model import Job
                placeholder_job = Job(
                    platform="email", company_name=email.sender, title=email.subject,
                )
                text = format_shortlist_alert(placeholder_job, email.body[:300])
                asyncio.run(notifier.send(text))

        conn.close()
        logger.info("Email tracking: processed %d emails.", len(emails))
    except Exception as exc:
        logger.error("Email tracking job failed: %s", exc)
        _notify_health_failure("Email tracking", str(exc))


def daily_report_job() -> None:
    """Sends the end-of-day summary to Telegram."""
    try:
        conn = _get_conn()
        stats = get_today_stats(conn)
        conn.close()

        notifier = TelegramNotifier()
        text = format_daily_summary(stats)
        asyncio.run(notifier.send(text))
        logger.info("Daily report sent.")
    except Exception as exc:
        logger.error("Daily report job failed: %s", exc)
        _notify_health_failure("Daily report", str(exc))


def health_check_job() -> None:
    """Lightweight check that the database and config are still reachable.
    Does NOT message Telegram on success -- only on failure -- to avoid
    spamming the user every 15 minutes with "all good" pings."""
    try:
        conn = _get_conn()
        conn.execute("SELECT 1")
        conn.close()
        load_profile()
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        _notify_health_failure("Health check", str(exc))


def _notify_health_failure(component: str, error: str) -> None:
    try:
        notifier = TelegramNotifier()
        text = format_health_check_failure(component, error)
        asyncio.run(notifier.send(text))
    except Exception:
        pass  # never let the notifier itself crash anything
