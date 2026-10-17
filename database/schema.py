"""
SQLite schema initialization for the Job Search Autopilot.

Run this module directly to create/upgrade the database:
    python -m database.schema
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS companies (
    company_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    website         TEXT,
    ats_type        TEXT,
    board_token     TEXT,
    industry        TEXT,
    size            TEXT,
    description     TEXT,
    researched_at   TEXT,
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id          TEXT PRIMARY KEY,         -- our canonical dedup id (hash)
    external_id     TEXT,
    platform        TEXT NOT NULL,
    company_id      INTEGER,
    company_name    TEXT NOT NULL,
    title           TEXT NOT NULL,
    location        TEXT,
    remote_type     TEXT,
    salary_min      REAL,
    salary_max      REAL,
    currency        TEXT,
    employment_type TEXT,
    experience_level TEXT,
    job_url         TEXT,
    apply_url       TEXT,
    description     TEXT,
    skills          TEXT,                      -- JSON list
    posting_date    TEXT,
    discovered_at   TEXT NOT NULL,
    source          TEXT,
    ats_type        TEXT,
    status          TEXT NOT NULL DEFAULT 'DISCOVERED',
    match_score     REAL,
    match_reasoning TEXT,                      -- JSON
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

CREATE TABLE IF NOT EXISTS job_sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL,
    platform        TEXT NOT NULL,
    source_url      TEXT,
    discovered_at   TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE TABLE IF NOT EXISTS resumes (
    resume_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL,
    file_path_pdf   TEXT,
    file_path_docx  TEXT,
    cover_note      TEXT,
    base_resume_hash TEXT,
    provider_used   TEXT,
    keywords_emphasized TEXT,                  -- JSON list
    created_at      TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE TABLE IF NOT EXISTS applications (
    application_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL UNIQUE,      -- one application per job, enforced
    resume_id       INTEGER,
    platform        TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'DISCOVERED',
    autonomy_level  TEXT,                      -- AUTO_EXECUTE | APPROVAL_REQUIRED | ACTION_REQUIRED | SKIPPED | FAILED
    submitted_at    TEXT,
    screenshot_path TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    FOREIGN KEY (resume_id) REFERENCES resumes(resume_id)
);

CREATE TABLE IF NOT EXISTS application_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id  INTEGER,
    job_id          TEXT,
    timestamp       TEXT NOT NULL,
    module          TEXT,
    action          TEXT NOT NULL,
    status          TEXT,
    details          TEXT,
    error           TEXT,
    duration_ms     INTEGER,
    FOREIGN KEY (application_id) REFERENCES applications(application_id)
);

CREATE TABLE IF NOT EXISTS emails (
    email_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT,
    sender          TEXT,
    subject         TEXT,
    received_at     TEXT NOT NULL,
    classification  TEXT,                      -- shortlisted | interview | assessment | rejection | other
    confidence      REAL,
    summary         TEXT,
    raw_snippet     TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id         TEXT PRIMARY KEY,
    task_type       TEXT NOT NULL,
    priority        INTEGER DEFAULT 5,
    status          TEXT NOT NULL DEFAULT 'PENDING',
    payload         TEXT,                      -- JSON
    result          TEXT,                      -- JSON
    error           TEXT,
    retry_count     INTEGER DEFAULT 0,
    max_retries     INTEGER DEFAULT 3,
    created_at      TEXT NOT NULL,
    next_run_at     TEXT,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL,
    application_id  INTEGER,
    status          TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING | APPROVED | SKIPPED
    requested_at    TEXT NOT NULL,
    resolved_at     TEXT,
    payload         TEXT,                      -- JSON snapshot shown to the user
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    mode            TEXT,                       -- dry-run | live
    jobs_discovered INTEGER DEFAULT 0,
    jobs_scored     INTEGER DEFAULT 0,
    resumes_generated INTEGER DEFAULT 0,
    applications_submitted INTEGER DEFAULT 0,
    errors          INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS errors (
    error_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    module          TEXT,
    category        TEXT,                       -- TRANSIENT | PERMANENT | AUTHENTICATION | SITE_CHANGED | ...
    message         TEXT,
    job_id          TEXT,
    resolved        INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_name);
CREATE INDEX IF NOT EXISTS idx_jobs_platform ON jobs(platform);
CREATE INDEX IF NOT EXISTS idx_applications_state ON applications(state);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_events_job ON application_events(job_id);
CREATE INDEX IF NOT EXISTS idx_emails_job ON emails(job_id);
"""


def init_db(db_path: str = "data/job_autopilot.db") -> sqlite3.Connection:
    """Create the database file and all tables/indexes if they don't exist."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


if __name__ == "__main__":
    connection = init_db()
    cursor = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    )
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Database initialized with {len(tables)} tables:")
    for t in tables:
        print(f"  - {t}")
    connection.close()
