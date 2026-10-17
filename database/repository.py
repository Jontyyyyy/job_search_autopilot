"""
The persistence layer. Every other module (discovery, matcher, resume
builder, email tracker) produces plain Python objects; this module is the
only place that writes them into SQLite, and the only place the dashboard
reads them back from.

Keeping all database access in one file means the schema can change without
touching the modules that produce the data, and makes this layer directly
testable with a throwaway in-memory database.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from discovery.job_model import Job
from ai.matcher import MatchResult
from resume.tailor import TailoredResume
from email_tracking.parser import ParsedEmail
from email_tracking.classifier import EmailClassification


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- jobs ----------

def save_job(conn: sqlite3.Connection, job: Job, match: MatchResult | None = None) -> None:
    """Insert a job, or update its match score if it already exists
    (same job_id = same real-world opportunity, per the dedup logic)."""
    existing = conn.execute("SELECT job_id FROM jobs WHERE job_id = ?", (job.job_id,)).fetchone()

    match_score = match.overall_score if match else None
    match_reasoning = json.dumps(match.to_dict()) if match else None

    if existing:
        conn.execute(
            "UPDATE jobs SET match_score = ?, match_reasoning = ? WHERE job_id = ?",
            (match_score, match_reasoning, job.job_id),
        )
    else:
        conn.execute(
            """INSERT INTO jobs (
                job_id, external_id, platform, company_name, title, location,
                remote_type, salary_min, salary_max, currency, employment_type,
                experience_level, job_url, apply_url, description, skills,
                posting_date, discovered_at, source, ats_type, status,
                match_score, match_reasoning
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job.job_id, job.external_id, job.platform, job.company_name, job.title,
                job.location, job.remote_type, job.salary_min, job.salary_max, job.currency,
                job.employment_type, job.experience_level, job.job_url, job.apply_url,
                job.description, json.dumps(job.skills), job.posting_date, job.discovered_at,
                job.source, job.ats_type, "DISCOVERED" if not match else "MATCHED",
                match_score, match_reasoning,
            ),
        )
    conn.commit()


def update_job_status(conn: sqlite3.Connection, job_id: str, status: str) -> None:
    conn.execute("UPDATE jobs SET status = ? WHERE job_id = ?", (status, job_id))
    conn.commit()


def get_existing_job_ids(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Returns (job_id, canonical_signature) pairs for the Deduplicator to
    load before a discovery run. Signature is reconstructed from stored
    fields since we don't store it directly."""
    rows = conn.execute("SELECT job_id, company_name, title, location FROM jobs").fetchall()
    import re

    def _norm(text: str) -> str:
        text = (text or "").lower().strip()
        text = re.sub(r"[^\w\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    return [
        (job_id, "|".join([_norm(company), _norm(title), _norm(location)]))
        for job_id, company, title, location in rows
    ]


def list_jobs(conn: sqlite3.Connection, status: str | None = None, limit: int = 200) -> list[dict]:
    query = "SELECT * FROM jobs"
    params: tuple = ()
    if status:
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY discovered_at DESC LIMIT ?"
    params = params + (limit,)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ---------- resumes ----------

def save_resume(
    conn: sqlite3.Connection, job_id: str, resume: TailoredResume,
    file_path_pdf: str, file_path_docx: str | None = None,
) -> int:
    cursor = conn.execute(
        """INSERT INTO resumes (
            job_id, file_path_pdf, file_path_docx, cover_note,
            keywords_emphasized, created_at
        ) VALUES (?,?,?,?,?,?)""",
        (
            job_id, file_path_pdf, file_path_docx, resume.summary,
            json.dumps(resume.keywords_emphasized), _now_iso(),
        ),
    )
    conn.commit()
    return cursor.lastrowid


# ---------- applications ----------

def create_application(
    conn: sqlite3.Connection, job_id: str, platform: str,
    resume_id: int | None = None, autonomy_level: str = "APPROVAL_REQUIRED",
) -> int:
    now = _now_iso()
    cursor = conn.execute(
        """INSERT INTO applications (
            job_id, resume_id, platform, state, autonomy_level, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?)""",
        (job_id, resume_id, platform, "DISCOVERED", autonomy_level, now, now),
    )
    conn.commit()
    return cursor.lastrowid


def update_application_state(conn: sqlite3.Connection, application_id: int, state: str) -> None:
    conn.execute(
        "UPDATE applications SET state = ?, updated_at = ? WHERE application_id = ?",
        (state, _now_iso(), application_id),
    )
    conn.commit()


def list_applications(conn: sqlite3.Connection, limit: int = 200) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT a.*, j.title, j.company_name, j.platform as job_platform
           FROM applications a JOIN jobs j ON a.job_id = j.job_id
           ORDER BY a.updated_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------- emails ----------

def save_email(
    conn: sqlite3.Connection, email: ParsedEmail,
    classification: EmailClassification, job_id: str | None = None,
) -> None:
    # avoid duplicate rows for the same message if the fetch loop overlaps
    existing = None
    if email.message_id:
        existing = conn.execute(
            "SELECT email_id FROM emails WHERE job_id IS ? AND sender = ? AND subject = ? AND received_at = ?",
            (job_id, email.sender, email.subject, email.date),
        ).fetchone()
    if existing:
        return

    conn.execute(
        """INSERT INTO emails (
            job_id, sender, subject, received_at, classification,
            confidence, summary, raw_snippet
        ) VALUES (?,?,?,?,?,?,?,?)""",
        (
            job_id, email.sender, email.subject, email.date or _now_iso(),
            classification.category, classification.confidence,
            email.body[:200], email.body[:1000],
        ),
    )
    conn.commit()


def list_emails(conn: sqlite3.Connection, classification: str | None = None, limit: int = 100) -> list[dict]:
    query = "SELECT * FROM emails"
    params: tuple = ()
    if classification:
        query += " WHERE classification = ?"
        params = (classification,)
    query += " ORDER BY received_at DESC LIMIT ?"
    params = params + (limit,)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ---------- dashboard aggregate stats ----------

def get_today_stats(conn: sqlite3.Connection) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    conn.row_factory = sqlite3.Row

    jobs_discovered = conn.execute(
        "SELECT COUNT(*) as c FROM jobs WHERE discovered_at LIKE ?", (f"{today}%",)
    ).fetchone()["c"]

    jobs_scored = conn.execute(
        "SELECT COUNT(*) as c FROM jobs WHERE match_score IS NOT NULL AND discovered_at LIKE ?",
        (f"{today}%",),
    ).fetchone()["c"]

    resumes_generated = conn.execute(
        "SELECT COUNT(*) as c FROM resumes WHERE created_at LIKE ?", (f"{today}%",)
    ).fetchone()["c"]

    applications_submitted = conn.execute(
        "SELECT COUNT(*) as c FROM applications WHERE state = 'SUBMITTED' AND updated_at LIKE ?",
        (f"{today}%",),
    ).fetchone()["c"]

    shortlists = conn.execute(
        "SELECT COUNT(*) as c FROM emails WHERE classification = 'shortlisted' AND received_at LIKE ?",
        (f"{today}%",),
    ).fetchone()["c"]

    interviews = conn.execute(
        "SELECT COUNT(*) as c FROM emails WHERE classification = 'interview' AND received_at LIKE ?",
        (f"{today}%",),
    ).fetchone()["c"]

    rejections = conn.execute(
        "SELECT COUNT(*) as c FROM emails WHERE classification = 'rejection' AND received_at LIKE ?",
        (f"{today}%",),
    ).fetchone()["c"]

    pending_actions = conn.execute(
        "SELECT COUNT(*) as c FROM applications WHERE state = 'ACTION_REQUIRED'"
    ).fetchone()["c"]

    return {
        "jobs_discovered": jobs_discovered,
        "jobs_scored": jobs_scored,
        "resumes_generated": resumes_generated,
        "applications_submitted": applications_submitted,
        "shortlists": shortlists,
        "interviews": interviews,
        "rejections": rejections,
        "pending_actions": pending_actions,
        "errors": 0,
    }


def get_pipeline_counts(conn: sqlite3.Connection) -> dict[str, int]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT status, COUNT(*) as c FROM jobs GROUP BY status"
    ).fetchall()
    return {row["status"]: row["c"] for row in rows}
