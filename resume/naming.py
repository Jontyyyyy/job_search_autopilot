"""Generates safe, consistent filenames for tailored resumes."""
from __future__ import annotations

import re
from datetime import date

from discovery.job_model import Job


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "_", text).strip("_")
    return text or "unknown"


def resume_filename(job: Job, extension: str = "pdf", on_date: date | None = None) -> str:
    on_date = on_date or date.today()
    company = _slugify(job.company_name)
    title = _slugify(job.title)
    date_str = on_date.isoformat()
    return f"{company}_{title}_{date_str}.{extension}"
