import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.greenhouse import GreenhouseAdapter
from adapters.lever import LeverAdapter


GREENHOUSE_SAMPLE_RESPONSE = {
    "jobs": [
        {
            "id": 12345,
            "title": "Backend Engineer",
            "location": {"name": "Mumbai, India"},
            "content": "<p>We need <b>Python</b> and Django experience.</p>",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
            "updated_at": "2026-01-01T00:00:00Z",
        },
        {
            # malformed: missing title -- must be skipped, not crash the run
            "id": 999,
            "location": {"name": "Remote"},
        },
    ]
}

LEVER_SAMPLE_RESPONSE = [
    {
        "id": "abc-123",
        "text": "Frontend Engineer",
        "categories": {"location": "Remote", "commitment": "Full-time"},
        "descriptionPlain": "React and TypeScript required.",
        "hostedUrl": "https://jobs.lever.co/acme/abc-123",
        "applyUrl": "https://jobs.lever.co/acme/abc-123/apply",
        "createdAt": 1700000000000,
    },
    {
        # malformed: missing text -- must be skipped
        "id": "def-456",
        "categories": {},
    },
]


def _mock_response(json_data, status_ok=True):
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_data
    if status_ok:
        mock_resp.raise_for_status.return_value = None
    else:
        import requests
        mock_resp.raise_for_status.side_effect = requests.RequestException("boom")
    return mock_resp


def test_greenhouse_normalizes_valid_job_and_skips_malformed():
    adapter = GreenhouseAdapter()
    with patch("adapters.greenhouse.requests.get", return_value=_mock_response(GREENHOUSE_SAMPLE_RESPONSE)):
        jobs = adapter.discover_jobs(board_token="acme", company_name="Acme Corp")

    assert len(jobs) == 1  # the malformed record was skipped, not crashed on
    job = jobs[0]
    assert job.title == "Backend Engineer"
    assert job.company_name == "Acme Corp"
    assert job.external_id == "12345"
    assert "Python" in job.description  # HTML stripped
    assert "<b>" not in job.description
    assert job.platform == "greenhouse"
    assert job.ats_type == "greenhouse"


def test_greenhouse_remote_detection():
    adapter = GreenhouseAdapter()
    payload = {
        "jobs": [{
            "id": 1, "title": "DevOps Engineer",
            "location": {"name": "Remote - India"},
            "content": "", "absolute_url": "", "updated_at": "",
        }]
    }
    with patch("adapters.greenhouse.requests.get", return_value=_mock_response(payload)):
        jobs = adapter.discover_jobs(board_token="acme")
    assert jobs[0].remote_type == "remote"


def test_greenhouse_network_failure_returns_empty_not_raises():
    adapter = GreenhouseAdapter()
    with patch("adapters.greenhouse.requests.get", return_value=_mock_response({}, status_ok=False)):
        jobs = adapter.discover_jobs(board_token="acme")
    assert jobs == []  # must degrade gracefully, never crash the whole run


def test_lever_normalizes_valid_job_and_skips_malformed():
    adapter = LeverAdapter()
    with patch("adapters.lever.requests.get", return_value=_mock_response(LEVER_SAMPLE_RESPONSE)):
        jobs = adapter.discover_jobs(board_token="acme", company_name="Acme Corp")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Frontend Engineer"
    assert job.external_id == "abc-123"
    assert job.remote_type == "remote"
    assert job.platform == "lever"
    assert job.apply_url.endswith("/apply")


def test_lever_network_failure_returns_empty_not_raises():
    adapter = LeverAdapter()
    with patch("adapters.lever.requests.get", return_value=_mock_response({}, status_ok=False)):
        jobs = adapter.discover_jobs(board_token="acme")
    assert jobs == []


def test_lever_non_list_payload_returns_empty():
    adapter = LeverAdapter()
    with patch("adapters.lever.requests.get", return_value=_mock_response({"error": "not found"})):
        jobs = adapter.discover_jobs(board_token="nonexistent")
    assert jobs == []
