"""
The core discovery -> score -> tailor cycle, as a reusable function.

Both agent/run_once.py (manual one-shot run) and scheduler/jobs.py
(automatic repeating run) call this same function, so the actual pipeline
logic lives in exactly one place.
"""
from __future__ import annotations

import logging
import sqlite3

from database.repository import save_job, get_existing_job_ids, save_resume
from discovery.dedupe import Deduplicator
from adapters.greenhouse import GreenhouseAdapter
from adapters.lever import LeverAdapter
from ai.matcher import score_job
from resume.tailor import tailor_resume
from resume.pdf_export import export_resume_pdf
from resume.naming import resume_filename

logger = logging.getLogger(__name__)

ADAPTER_MAP = {
    "greenhouse": GreenhouseAdapter(),
    "lever": LeverAdapter(),
}


def run_discovery_cycle(conn: sqlite3.Connection, profile: dict, companies: list[dict]) -> dict:
    """Runs one full discovery -> dedupe -> score -> tailor cycle against the
    given companies, writing results into conn. Returns a stats dict (used
    for both console output and the daily Telegram summary).

    Never raises on a single company or job failing -- logs and continues,
    so one bad adapter or malformed record never stops the whole cycle."""
    threshold = profile.get("thresholds", {}).get("job_match_threshold", 60)

    dedupe = Deduplicator()
    dedupe.load_existing(get_existing_job_ids(conn))

    stats = {
        "jobs_discovered": 0, "jobs_new": 0, "jobs_scored": 0,
        "resumes_generated": 0, "strong_matches": [],
    }

    for company in companies:
        ats_type = company.get("ats_type")
        adapter = ADAPTER_MAP.get(ats_type)
        if adapter is None:
            logger.warning("Skipping %s: unsupported ats_type '%s'", company.get("name"), ats_type)
            continue

        try:
            jobs = adapter.discover_jobs(
                board_token=company.get("board_token"), company_name=company.get("name"),
            )
        except Exception as exc:
            logger.error("Discovery failed for %s: %s", company.get("name"), exc)
            continue

        stats["jobs_discovered"] += len(jobs)

        for job in jobs:
            try:
                result = dedupe.check(job)
                if result.is_duplicate:
                    continue
                dedupe.register(job)
                stats["jobs_new"] += 1

                match = score_job(job, profile)
                save_job(conn, job, match)
                stats["jobs_scored"] += 1

                if match.overall_score >= threshold:
                    resume = tailor_resume(job, profile)
                    filename = resume_filename(job)
                    pdf_path = export_resume_pdf(resume, f"output/resumes/{filename}")
                    save_resume(conn, job.job_id, resume, pdf_path)
                    stats["resumes_generated"] += 1
                    stats["strong_matches"].append((job, match.overall_score))
            except Exception as exc:
                # one malformed job must never stop the whole cycle
                logger.error("Failed to process job %r: %s", getattr(job, "title", "?"), exc)
                continue

    return stats
