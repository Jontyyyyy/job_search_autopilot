"""
Formats every notification the agent sends, as plain functions returning
strings (Telegram Markdown). Kept separate from the actual sending code
(telegram_bot.py) so this logic is fully testable without a network call,
a bot token, or the telegram library itself.
"""
from __future__ import annotations

from discovery.job_model import Job
from ai.matcher import MatchResult


def _escape_markdown(text: str) -> str:
    """Escape characters that break Telegram's legacy Markdown parser."""
    if not text:
        return text
    for ch in ["_", "*", "`", "["]:
        text = text.replace(ch, f"\\{ch}")
    return text


def format_job_match_alert(job: Job, match: MatchResult) -> str:
    """A single strong job match worth telling the user about right away."""
    title = _escape_markdown(job.title)
    company = _escape_markdown(job.company_name)
    location = _escape_markdown(job.location or "Not specified")

    lines = [
        f"*New strong match: {match.overall_score:.0f}/100*",
        f"*{title}* at *{company}*",
        f"📍 {location}",
        "",
        match.reasoning,
    ]
    if job.job_url:
        lines.append(f"\n[View job]({job.job_url})")
    return "\n".join(lines)


def format_shortlist_alert(job: Job, email_summary: str) -> str:
    """Highest-priority alert: the user got shortlisted/an interview invite."""
    title = _escape_markdown(job.title)
    company = _escape_markdown(job.company_name)
    return (
        f"🎉 *You've been shortlisted\\!*\n"
        f"*{title}* at *{company}*\n\n"
        f"{email_summary}"
    )


def format_action_required_alert(job: Job, reason: str) -> str:
    """A task got blocked (CAPTCHA, login wall, unknown form field, etc.)
    and needs a human to unblock it."""
    title = _escape_markdown(job.title)
    company = _escape_markdown(job.company_name)
    return (
        f"⚠️ *Action needed: {title} at {company}*\n\n"
        f"Reason: {reason}\n"
        f"Everything else is continuing normally — this is the only task waiting on you."
    )


def format_batch_approval_request(jobs_with_scores: list[tuple[Job, float]]) -> str:
    """Daily batch of ready-to-submit applications waiting for one approval."""
    count = len(jobs_with_scores)
    lines = [f"*{count} application{'s' if count != 1 else ''} ready for your approval:*\n"]
    for job, score in jobs_with_scores:
        title = _escape_markdown(job.title)
        company = _escape_markdown(job.company_name)
        lines.append(f"• *{title}* at *{company}* — {score:.0f}/100")
    lines.append("\nReply /approve\\_all to send all, or /pending to review one by one.")
    return "\n".join(lines)


def format_daily_summary(stats: dict) -> str:
    """End-of-day report: what the agent did today."""
    lines = [
        "*Today's summary*",
        "",
        f"🔍 Jobs discovered: {stats.get('jobs_discovered', 0)}",
        f"📊 Jobs scored: {stats.get('jobs_scored', 0)}",
        f"📄 Resumes generated: {stats.get('resumes_generated', 0)}",
        f"📨 Applications submitted: {stats.get('applications_submitted', 0)}",
        f"⭐ Shortlists: {stats.get('shortlists', 0)}",
        f"🎤 Interviews: {stats.get('interviews', 0)}",
        f"❌ Rejections: {stats.get('rejections', 0)}",
        f"⚠️ Pending your action: {stats.get('pending_actions', 0)}",
    ]
    if stats.get("errors", 0):
        lines.append(f"\n🔧 {stats['errors']} task(s) hit an error and were logged for review.")
    return "\n".join(lines)


def format_health_check_failure(component: str, error: str) -> str:
    """The agent itself hit a problem (not a job-specific one) -- a provider
    outage, database issue, etc."""
    return (
        f"🔧 *Agent health issue: {component}*\n\n"
        f"{error}\n\n"
        f"The agent will keep retrying automatically. This is informational only."
    )
