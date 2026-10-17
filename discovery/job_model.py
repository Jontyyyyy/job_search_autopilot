"""
Canonical Job data model.

Every collector (email, Greenhouse, Lever, career-page scraper, etc.) must
normalize its raw output into a Job instance before it touches the database.
This keeps every downstream module (matcher, resume builder, applicant,
dashboard) agnostic to where a job actually came from.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation noise for comparison."""
    value = value.lower().strip()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


@dataclass
class Job:
    platform: str                      # "linkedin" | "naukri" | "indeed" | "greenhouse" | ...
    company_name: str
    title: str
    job_url: str = ""
    apply_url: str = ""
    external_id: Optional[str] = None
    location: str = ""
    remote_type: str = ""              # "remote" | "hybrid" | "onsite" | ""
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: str = ""
    employment_type: str = ""
    experience_level: str = ""
    description: str = ""
    skills: list[str] = field(default_factory=list)
    posting_date: str = ""
    source: str = ""
    ats_type: str = ""
    discovered_at: str = field(default_factory=_now_iso)

    job_id: str = field(init=False, default="")

    def __post_init__(self) -> None:
        self.job_id = self.compute_job_id()

    def compute_job_id(self) -> str:
        """
        Deterministic dedup key.

        Priority:
        1. platform + external_id, when the platform gives us a stable ID
           (Greenhouse/Lever/Ashby job IDs are stable and best).
        2. Otherwise, a normalized hash of company + title + location, so the
           *same* job re-scraped tomorrow, or seen on a second platform with
           near-identical text, collapses to one record.
        """
        if self.external_id:
            raw = f"{self.platform}:{self.external_id}"
        else:
            raw = "|".join([
                _normalize_text(self.company_name),
                _normalize_text(self.title),
                _normalize_text(self.location),
            ])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def canonical_signature(self) -> str:
        """
        A looser signature used for cross-platform fuzzy dedup (same job
        posted on LinkedIn AND the company's Greenhouse board). Does not
        include platform or external_id on purpose.
        """
        return "|".join([
            _normalize_text(self.company_name),
            _normalize_text(self.title),
            _normalize_text(self.location),
        ])

    def to_dict(self) -> dict:
        d = asdict(self)
        d["skills"] = json.dumps(self.skills)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @staticmethod
    def required_fields_present(d: dict) -> bool:
        return bool(d.get("platform") and d.get("company_name") and d.get("title"))
