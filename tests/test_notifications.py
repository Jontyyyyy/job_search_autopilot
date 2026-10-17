import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from discovery.job_model import Job
from ai.matcher import MatchResult
from notifications.message_formatting import (
    format_job_match_alert,
    format_shortlist_alert,
    format_action_required_alert,
    format_batch_approval_request,
    format_daily_summary,
    format_health_check_failure,
)


def make_job(**overrides) -> Job:
    defaults = dict(platform="greenhouse", company_name="Acme Corp", title="Backend Developer",
                      location="Mumbai", job_url="https://example.com/job/1")
    defaults.update(overrides)
    return Job(**defaults)


def make_match(score=85.0) -> MatchResult:
    return MatchResult(
        overall_score=score, skill_score=90, experience_score=80,
        location_score=100, salary_score=70,
        matched_skills=["python", "react"], missing_skills=[],
        disqualifiers=[], reasoning="Skill match 90%, experience fit 80%.",
    )


def test_job_match_alert_includes_score_and_job_details():
    job = make_job()
    match = make_match(85.0)
    text = format_job_match_alert(job, match)
    assert "85" in text
    assert "Backend Developer" in text
    assert "Acme Corp" in text
    assert job.job_url in text


def test_job_match_alert_escapes_markdown_in_company_name():
    job = make_job(company_name="Acme_Corp*Inc")
    match = make_match()
    text = format_job_match_alert(job, match)
    # underscores and asterisks in the name must be escaped so Telegram
    # doesn't interpret them as formatting and break the message
    assert "Acme\\_Corp\\*Inc" in text


def test_shortlist_alert_includes_celebration_and_details():
    job = make_job(title="Senior Engineer")
    text = format_shortlist_alert(job, "They want to schedule a call next week.")
    assert "shortlisted" in text.lower()
    assert "Senior Engineer" in text
    assert "schedule a call" in text


def test_action_required_alert_explains_reason_and_reassures():
    job = make_job()
    text = format_action_required_alert(job, "CAPTCHA appeared on the application form")
    assert "CAPTCHA" in text
    assert "Acme Corp" in text
    assert "continuing normally" in text.lower()


def test_batch_approval_request_lists_all_jobs_with_scores():
    jobs = [
        (make_job(title="Backend Dev", company_name="Acme"), 88.0),
        (make_job(title="Frontend Dev", company_name="Globex"), 76.0),
    ]
    text = format_batch_approval_request(jobs)
    assert "2 applications" in text
    assert "Backend Dev" in text and "88" in text
    assert "Frontend Dev" in text and "76" in text


def test_batch_approval_request_singular_for_one_job():
    jobs = [(make_job(title="Backend Dev"), 88.0)]
    text = format_batch_approval_request(jobs)
    assert "1 application " in text  # singular, not "1 applications"


def test_daily_summary_includes_all_stats():
    stats = {
        "jobs_discovered": 50, "jobs_scored": 50, "resumes_generated": 5,
        "applications_submitted": 3, "shortlists": 1, "interviews": 0,
        "rejections": 2, "pending_actions": 1, "errors": 0,
    }
    text = format_daily_summary(stats)
    assert "50" in text
    assert "Shortlists: 1" in text
    assert "errors" not in text.lower()  # no error line when errors is 0


def test_daily_summary_flags_errors_when_present():
    stats = {"errors": 3}
    text = format_daily_summary(stats)
    assert "3 task(s) hit an error" in text


def test_daily_summary_handles_missing_keys_gracefully():
    text = format_daily_summary({})
    assert "0" in text  # defaults to 0, doesn't crash on missing keys


def test_health_check_failure_names_component_and_error():
    text = format_health_check_failure("Gemini API", "Rate limit exceeded")
    assert "Gemini API" in text
    assert "Rate limit exceeded" in text
    assert "retrying automatically" in text.lower()
