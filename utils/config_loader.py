"""
Loads and validates config/profile.yaml, config/settings.yaml and
config/companies.yaml so every other module gets a plain Python dict it can
trust, instead of re-parsing YAML everywhere.
"""
from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class ConfigError(Exception):
    pass


def _load_yaml(filename: str) -> dict:
    path = CONFIG_DIR / filename
    if not path.exists():
        raise ConfigError(f"Missing config file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def load_profile() -> dict:
    data = _load_yaml("profile.yaml")
    required_top_level = ["personal", "role", "skills", "thresholds"]
    missing = [k for k in required_top_level if k not in data]
    if missing:
        raise ConfigError(f"profile.yaml is missing required sections: {missing}")
    return data


def load_settings() -> dict:
    return _load_yaml("settings.yaml")


def load_companies() -> list[dict]:
    data = _load_yaml("companies.yaml")
    return data.get("companies", [])


def load_base_resume_text() -> str:
    path = CONFIG_DIR / "base_resume.md"
    if not path.exists():
        raise ConfigError(f"Missing config file: {path}")
    return path.read_text(encoding="utf-8")
