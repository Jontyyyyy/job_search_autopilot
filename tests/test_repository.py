import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
import pytest

from database.schema import SCHEMA_SQL
from database.repository import (
    save_job, update_job_status, list_jobs, get_existing_job_ids,
    save_resume, create_application, update_application_state, list_applications,
    save_email, list_emails, get_today_stats, get_pipeline_counts,
)
from discovery.job_model import Job
from ai.matcher import MatchResult
from resume.tailor import TailoredResume
from email_tracking.parser import ParsedEmail
from email_tracking.classifier import EmailClassification


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA_SQL)
    yield connection
    connection.close()


def make_job(**overrides) -> Job:
    defaults = dict(platform="greenhouse", company_name="Acme", title="Backend Developer",
                      external_id="123")
    defaults.update(overrides)
    return Job(**defaults)


def make_match(score=85.0) -> MatchResult:
    return MatchResult(overall_score=score, skill_score=90, experience_score=80,
                         location_score=100, salary_score=70, matched_skills=["python"])


# ---------- jobs ----------

def test_save_and_list_job(conn):
    job = make_job()
    save_job(conn, job)
    jobs = list_jobs(conn)
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Backend Developer"
    assert jobs[0]["status"] == "DISCOVERED"


def test_save_job_with_match_sets_status_matched(conn):
    job = make_job()
    match = make_match(85.0)
    save_job(conn, job, match)
    jobs = list_jobs(conn)
    assert jobs[0]["status"] == "MATCHED"
    assert jobs[0]["match_score"] == 85.0


def test_save_job_twice_updates_not_duplicates(conn):
    job = make_job()
    save_job(conn, job)
    save_job(conn, job, make_match(90.0))  # same job_id, now with a match
    jobs = list_jobs(conn)
    assert len(jobs) == 1  # not duplicated
    assert jobs[0]["match_score"] == 90.0


def test_update_job_status(conn):
    job = make_job()
    save_job(conn, job)
    update_job_status(conn, job.job_id, "APPLIED")
    jobs = list_jobs(conn)
    assert jobs[0]["status"] == "APPLIED"


def test_list_jobs_filters_by_status(conn):
    save_job(conn, make_job(external_id="1", title="Job A"))
    job_b = make_job(external_id="2", title="Job B")
    save_job(conn, job_b)
    update_job_status(conn, job_b.job_id, "APPLIED")

    applied_jobs = list_jobs(conn, status="APPLIED")
    assert len(applied_jobs) == 1
    assert applied_jobs[0]["title"] == "Job B"


def test_get_existing_job_ids_for_dedup(conn):
    job = make_job()
    save_job(conn, job)
    existing = get_existing_job_ids(conn)
    assert len(existing) == 1
    assert existing[0][0] == job.job_id


# ---------- resumes ----------

def test_save_resume(conn):
    job = make_job()
    save_job(conn, job)
    resume = TailoredResume(
        full_name="Test User", contact_line="test@example.com", summary="A summary",
        ordered_skills={}, ordered_projects=[], education=[], certifications=[],
        languages=[], keywords_emphasized=["python", "django"],
    )
    resume_id = save_resume(conn, job.job_id, resume, "/tmp/resume.pdf")
    assert resume_id is not None and resume_id > 0


# ---------- applications ----------

def test_create_and_update_application(conn):
    job = make_job()
    save_job(conn, job)
    app_id = create_application(conn, job.job_id, platform="greenhouse")
    assert app_id > 0

    update_application_state(conn, app_id, "SUBMITTED")
    apps = list_applications(conn)
    assert apps[0]["state"] == "SUBMITTED"
    assert apps[0]["title"] == "Backend Developer"  # joined from jobs table


# ---------- emails ----------

def test_save_and_list_email(conn):
    job = make_job()
    save_job(conn, job)
    email = ParsedEmail(sender="recruiter@acme.com", subject="Interview invite",
                          body="We'd like to interview you.", date="2026-01-01", message_id="<1@acme.com>")
    classification = EmailClassification(category="interview", confidence=0.9, matched_keywords=["interview"])
    save_email(conn, email, classification, job_id=job.job_id)

    emails = list_emails(conn)
    assert len(emails) == 1
    assert emails[0]["classification"] == "interview"


def test_save_email_avoids_duplicates(conn):
    email = ParsedEmail(sender="recruiter@acme.com", subject="Interview invite",
                          body="Body text", date="2026-01-01", message_id="<1@acme.com>")
    classification = EmailClassification(category="interview", confidence=0.9, matched_keywords=[])
    save_email(conn, email, classification)
    save_email(conn, email, classification)  # identical, should not duplicate

    emails = list_emails(conn)
    assert len(emails) == 1


def test_list_emails_filters_by_classification(conn):
    e1 = ParsedEmail(sender="a@x.com", subject="s1", body="b1", date="2026-01-01", message_id="<1>")
    e2 = ParsedEmail(sender="b@x.com", subject="s2", body="b2", date="2026-01-02", message_id="<2>")
    save_email(conn, e1, EmailClassification(category="rejection", confidence=0.8))
    save_email(conn, e2, EmailClassification(category="interview", confidence=0.9))

    interviews = list_emails(conn, classification="interview")
    assert len(interviews) == 1
    assert interviews[0]["sender"] == "b@x.com"


# ---------- dashboard stats ----------

def test_get_today_stats_counts_todays_activity(conn):
    job = make_job()
    save_job(conn, job, make_match(80.0))

    stats = get_today_stats(conn)
    assert stats["jobs_discovered"] == 1
    assert stats["jobs_scored"] == 1


def test_get_pipeline_counts_groups_by_status(conn):
    save_job(conn, make_job(external_id="1"))
    job2 = make_job(external_id="2")
    save_job(conn, job2)
    update_job_status(conn, job2.job_id, "APPLIED")

    counts = get_pipeline_counts(conn)
    assert counts.get("DISCOVERED") == 1
    assert counts.get("APPLIED") == 1
