"""
Lever public job-board adapter.

Lever also exposes a free, public, unauthenticated JSON API:

    https://api.lever.co/v0/postings/<board_token>?mode=json

Same rationale as Greenhouse: this is Lever's own documented public
endpoint -- LEVEL 1 in the decision engine, zero cost, no login, no scraping.
"""
from __future__ import annotations

import logging

import requests

from adapters.base import PlatformAdapter
from discovery.job_model import Job

logger = logging.getLogger(__name__)

LEVER_API_URL = "https://api.lever.co/v0/postings/{board_token}"


def _guess_remote_type(categories: dict) -> str:
    location = (categories.get("location") or "").lower()
    commitment = (categories.get("commitment") or "").lower()
    if "remote" in location or "remote" in commitment:
        return "remote"
    if "hybrid" in location:
        return "hybrid"
    return "onsite"


class LeverAdapter(PlatformAdapter):
    platform_name = "lever"

    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def capabilities(self) -> dict:
        return {
            "discovery": True,
            "application": False,
            "requires_browser": False,
            "requires_login": False,
        }

    def discover_jobs(self, board_token: str, company_name: str | None = None) -> list[Job]:
        url = LEVER_API_URL.format(board_token=board_token)
        try:
            response = requests.get(url, params={"mode": "json"}, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Lever fetch failed for %s: %s", board_token, exc)
            return []

        try:
            payload = response.json()
        except ValueError:
            logger.warning("Lever returned non-JSON for %s", board_token)
            return []

        if not isinstance(payload, list):
            return []

        jobs: list[Job] = []
        for raw in payload:
            job = self._normalize(raw, board_token, company_name)
            if job is not None:
                jobs.append(job)
        return jobs

    def _normalize(self, raw: dict, board_token: str, company_name: str | None) -> Job | None:
        title = raw.get("text")
        external_id = raw.get("id")
        if not title or not external_id:
            return None

        categories = raw.get("categories", {}) or {}
        description = raw.get("descriptionPlain") or raw.get("description") or ""

        return Job(
            platform=self.platform_name,
            company_name=company_name or board_token,
            title=title,
            external_id=str(external_id),
            location=categories.get("location", ""),
            remote_type=_guess_remote_type(categories),
            employment_type=categories.get("commitment", ""),
            description=description,
            job_url=raw.get("hostedUrl", ""),
            apply_url=raw.get("applyUrl", raw.get("hostedUrl", "")),
            posting_date=str(raw.get("createdAt", "")),
            source="lever_public_api",
            ats_type="lever",
        )
