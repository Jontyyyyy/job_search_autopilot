import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scheduler.main import parse_schedule_config


def test_parses_all_intervals_from_settings():
    settings = {
        "schedule": {
            "job_discovery_interval_hours": 4,
            "email_tracking_interval_minutes": 20,
            "health_check_interval_minutes": 10,
            "daily_report_time": "18:30",
        }
    }
    cfg = parse_schedule_config(settings)
    assert cfg["discovery_hours"] == 4
    assert cfg["email_minutes"] == 20
    assert cfg["health_minutes"] == 10
    assert cfg["report_hour"] == 18
    assert cfg["report_minute"] == 30


def test_uses_defaults_when_schedule_section_missing():
    cfg = parse_schedule_config({})
    assert cfg["discovery_hours"] == 3
    assert cfg["email_minutes"] == 30
    assert cfg["health_minutes"] == 15
    assert cfg["report_hour"] == 21
    assert cfg["report_minute"] == 0


def test_falls_back_to_default_time_on_malformed_time_string():
    settings = {"schedule": {"daily_report_time": "not-a-time"}}
    cfg = parse_schedule_config(settings)
    assert cfg["report_hour"] == 21
    assert cfg["report_minute"] == 0


def test_falls_back_to_default_time_when_time_is_wrong_type():
    settings = {"schedule": {"daily_report_time": None}}
    cfg = parse_schedule_config(settings)
    assert cfg["report_hour"] == 21
    assert cfg["report_minute"] == 0


def test_partial_settings_mix_custom_and_default_values():
    settings = {"schedule": {"job_discovery_interval_hours": 6}}
    cfg = parse_schedule_config(settings)
    assert cfg["discovery_hours"] == 6
    assert cfg["email_minutes"] == 30  # default, not overridden
