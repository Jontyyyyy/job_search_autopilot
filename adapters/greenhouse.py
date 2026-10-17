"""
Greenhouse public job-board adapter.

Greenhouse exposes a free, public, unauthenticated JSON API for any
company's job board:

    https://boards-api.greenhouse.io/v1/boards/<board_token>/jobs?content=true

No API key, no login, no scraping -- this is Greenhouse's own documented
public endpoint, which is exactly why Greenhouse is LEVEL 1 in the platform
decision engine (official structured endpoint) rather than LEVEL 4 (browser
automation).
"""
from __future__ import annotations

import logging
import re

import requests

from adapters.base import PlatformAdapter
from discovery.job_model import Job

logger = logging.getLogger(__name__)

GREENHOUSE_API_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _guess_remote_type(location_text: str) -> str:
    loc = (location_text or "").lower()
    if "remote" in loc:
        return "remote"
    if "hybrid" in loc:
        return "hybrid"
    return "onsite"


class GreenhouseAdapter(PlatformAdapter):
    platform_name = "greenhouse"

    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def capabilities(self) -> dict:
        return {
            "discovery": True,
            "application": False,  # application form automation is a separate, later module
            "requires_browser": False,
            "requires_login": False,
        }

    def discover_jobs(self, board_token: str, company_name: str | None = None) -> list[Job]:
        url = GREENHOUSE_API_URL.format(board_token=board_token)
        try:
            response = requests.get(
                url, params={"content": "true"}, timeout=self.timeout_seconds
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Greenhouse fetch failed for %s: %s", board_token, exc)
            return []

        try:
            payload = response.json()
        except ValueError:
            logger.warning("Greenhouse returned non-JSON for %s", board_token)
            return []

        jobs: list[Job] = []
        for raw in payload.get("jobs", []):
            job = self._normalize(raw, board_token, company_name)
            if job is not None:
                jobs.append(job)
        return jobs

    def _normalize(self, raw: dict, board_token: str, company_name: str | None) -> Job | None:
        title = raw.get("title")
        external_id = raw.get("id")
        if not title or external_id is None:
            return None  # skip malformed record, never crash the whole run

        location_name = (raw.get("location") or {}).get("name", "")
        description = _strip_html(raw.get("content", ""))

        return Job(
            platform=self.platform_name,
            company_name=company_name or board_token,
            title=title,
            external_id=str(external_id),
            location=location_name,
            remote_type=_guess_remote_type(location_name),
            description=description,
            job_url=raw.get("absolute_url", ""),
            apply_url=raw.get("absolute_url", ""),
            posting_date=raw.get("updated_at", ""),
            source="greenhouse_public_api",
            ats_type="greenhouse",
        )
