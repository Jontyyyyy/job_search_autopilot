"""
Runs one full discovery -> score -> save cycle against the companies in
config/companies.yaml, so the dashboard has real data to show.

Usage: python -m agent.run_once

This is intentionally a simple, single-pass script -- the full scheduler
(automatic, repeating, with retries and task recovery) is a later module.
This is the thing to run manually right now to see the dashboard come alive.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from database.schema import init_db
from database.repository import save_job, get_existing_job_ids, save_resume
from discovery.dedupe import Deduplicator
from adapters.greenhouse import GreenhouseAdapter
from adapters.lever import LeverAdapter
from ai.matcher import score_job
from resume.tailor import tailor_resume
from resume.pdf_export import export_resume_pdf
from resume.naming import resume_filename
from utils.config_loader import load_profile, load_companies


ADAPTER_MAP = {
    "greenhouse": GreenhouseAdapter(),
    "lever": LeverAdapter(),
}


def main() -> None:
    print("Loading profile and company list...")
    profile = load_profile()
    companies = load_companies()
    threshold = profile.get("thresholds", {}).get("job_match_threshold", 60)

    conn = init_db()
    dedupe = Deduplicator()
    dedupe.load_existing(get_existing_job_ids(conn))

    total_discovered = 0
    total_new = 0
    total_scored = 0
    total_resumes = 0

    for company in companies:
        ats_type = company.get("ats_type")
        adapter = ADAPTER_MAP.get(ats_type)
        if adapter is None:
            print(f"Skipping {company.get('name')}: unsupported ats_type '{ats_type}'")
            continue

        print(f"Discovering jobs at {company.get('name')} ({ats_type})...")
        jobs = adapter.discover_jobs(
            board_token=company.get("board_token"), company_name=company.get("name"),
        )
        total_discovered += len(jobs)

        for job in jobs:
            result = dedupe.check(job)
            if result.is_duplicate:
                continue
            dedupe.register(job)
            total_new += 1

            match = score_job(job, profile)
            save_job(conn, job, match)
            total_scored += 1

            if match.overall_score >= threshold:
                resume = tailor_resume(job, profile)
                filename = resume_filename(job)
                pdf_path = export_resume_pdf(resume, f"output/resumes/{filename}")
                save_resume(conn, job.job_id, resume, pdf_path)
                total_resumes += 1
                print(f"  -> Strong match ({match.overall_score:.0f}): {job.title} -- resume saved to {pdf_path}")

    conn.close()
    print(f"\nDone. Discovered: {total_discovered}, new: {total_new}, "
          f"scored: {total_scored}, resumes generated: {total_resumes}")


if __name__ == "__main__":
    main()
