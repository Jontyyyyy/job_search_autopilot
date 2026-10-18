import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
from unittest.mock import patch, MagicMock

from database.schema import SCHEMA_SQL
from agent.pipeline import run_discovery_cycle
from discovery.job_model import Job


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    return conn


def make_profile(threshold=60) -> dict:
    return {
        "personal": {"full_name": "Test User", "email": "t@example.com"},
        "role": {"target_roles": ["Backend Developer"], "experience_level": "entry"},
        "skills": {
            "programming_languages": ["Python"], "frameworks": ["Django"],
            "databases": ["PostgreSQL"], "tools": ["Git"], "other": [],
        },
        "location": {"preferred_locations": [], "remote_preference": "any", "willing_to_relocate": False},
        "compensation": {"expected_salary": 0, "minimum_salary": 0},
        "projects": [], "education": [], "certifications": [], "languages_spoken": [],
        "thresholds": {"job_match_threshold": threshold},
    }


def _mock_adapter(jobs: list[Job]):
    mock = MagicMock()
    mock.discover_jobs.return_value = jobs
    return mock


def test_discovers_and_scores_jobs_from_configured_companies():
    conn = make_conn()
    profile = make_profile()
    companies = [{"name": "Acme", "ats_type": "greenhouse", "board_token": "acme"}]

    job = Job(platform="greenhouse", company_name="Acme", title="Python Developer",
               description="Python Django PostgreSQL Git required.", external_id="1")

    with patch.dict("agent.pipeline.ADAPTER_MAP", {"greenhouse": _mock_adapter([job])}):
        stats = run_discovery_cycle(conn, profile, companies)

    assert stats["jobs_discovered"] == 1
    assert stats["jobs_new"] == 1
    assert stats["jobs_scored"] == 1
    conn.close()


def test_strong_match_generates_resume(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output" / "resumes").mkdir(parents=True)

    conn = make_conn()
    profile = make_profile(threshold=50)  # low threshold so our strong match clears it
    companies = [{"name": "Acme", "ats_type": "greenhouse", "board_token": "acme"}]

    job = Job(platform="greenhouse", company_name="Acme", title="Python Developer",
               description="Python Django PostgreSQL Git required.", external_id="1")

    with patch.dict("agent.pipeline.ADAPTER_MAP", {"greenhouse": _mock_adapter([job])}):
        stats = run_discovery_cycle(conn, profile, companies)

    assert stats["resumes_generated"] == 1
    assert len(stats["strong_matches"]) == 1
    conn.close()


def test_weak_match_does_not_generate_resume():
    conn = make_conn()
    profile = make_profile(threshold=90)  # high threshold, nothing should clear it
    companies = [{"name": "Acme", "ats_type": "greenhouse", "board_token": "acme"}]

    job = Job(platform="greenhouse", company_name="Acme", title="Java Architect",
               description="Java Kubernetes Scala required.", external_id="1")

    with patch.dict("agent.pipeline.ADAPTER_MAP", {"greenhouse": _mock_adapter([job])}):
        stats = run_discovery_cycle(conn, profile, companies)

    assert stats["resumes_generated"] == 0
    conn.close()


def test_already_known_job_is_not_rescored_or_reduplicated():
    conn = make_conn()
    profile = make_profile()
    companies = [{"name": "Acme", "ats_type": "greenhouse", "board_token": "acme"}]
    job = Job(platform="greenhouse", company_name="Acme", title="Python Developer",
               description="Python", external_id="1")

    with patch.dict("agent.pipeline.ADAPTER_MAP", {"greenhouse": _mock_adapter([job])}):
        run_discovery_cycle(conn, profile, companies)  # first run: discovers it
        stats2 = run_discovery_cycle(conn, profile, companies)  # second run: same job again

    assert stats2["jobs_discovered"] == 1  # adapter still returns it
    assert stats2["jobs_new"] == 0          # but it's not "new" the second time
    conn.close()


def test_unsupported_ats_type_is_skipped_not_crashed():
    conn = make_conn()
    profile = make_profile()
    companies = [{"name": "Weird Co", "ats_type": "workday", "board_token": "weird"}]

    stats = run_discovery_cycle(conn, profile, companies)  # no adapter registered for "workday"
    assert stats["jobs_discovered"] == 0
    conn.close()


def test_adapter_exception_does_not_crash_whole_cycle():
    conn = make_conn()
    profile = make_profile()
    companies = [
        {"name": "Broken Co", "ats_type": "greenhouse", "board_token": "broken"},
        {"name": "Good Co", "ats_type": "greenhouse", "board_token": "good"},
    ]

    broken_adapter = MagicMock()
    broken_adapter.discover_jobs.side_effect = Exception("network boom")

    good_job = Job(platform="greenhouse", company_name="Good Co", title="Dev", external_id="1")
    good_adapter = MagicMock()
    good_adapter.discover_jobs.return_value = [good_job]

    # Simulate per-company adapter selection by swapping the shared mock's
    # return behavior based on call count, since both companies use the
    # same ats_type in ADAPTER_MAP.
    call_order = [broken_adapter.discover_jobs, good_adapter.discover_jobs]
    combined = MagicMock()
    combined.discover_jobs.side_effect = [Exception("network boom"), [good_job]]

    with patch.dict("agent.pipeline.ADAPTER_MAP", {"greenhouse": combined}):
        stats = run_discovery_cycle(conn, profile, companies)

    # the broken company's exception must not have stopped the good one
    assert stats["jobs_discovered"] == 1
    conn.close()


def test_malformed_job_does_not_crash_whole_cycle():
    conn = make_conn()
    profile = make_profile()
    companies = [{"name": "Acme", "ats_type": "greenhouse", "board_token": "acme"}]

    good_job = Job(platform="greenhouse", company_name="Acme", title="Developer",
                     description="Python", external_id="1")
    bad_job = MagicMock()  # not a real Job -- accessing attributes will raise
    bad_job.job_id = "bad-id"
    bad_job.title = "Broken"

    with patch.dict("agent.pipeline.ADAPTER_MAP", {"greenhouse": _mock_adapter([bad_job, good_job])}):
        stats = run_discovery_cycle(conn, profile, companies)

    # the good job should still have been processed despite the bad one
    assert stats["jobs_scored"] >= 1
    conn.close()
