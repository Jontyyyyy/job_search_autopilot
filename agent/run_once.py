"""
Runs one full discovery -> score -> save cycle against the companies in
config/companies.yaml. The actual logic lives in agent/pipeline.py so it can
be shared with the scheduler (scheduler/jobs.py), which runs this same cycle
automatically on a timer instead of manually.

Usage: python -m agent.run_once
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.schema import init_db
from agent.pipeline import run_discovery_cycle
from utils.config_loader import load_profile, load_companies


def main() -> None:
    print("Loading profile and company list...")
    profile = load_profile()
    companies = load_companies()

    conn = init_db()

    for company in companies:
        print(f"Discovering jobs at {company.get('name')} ({company.get('ats_type')})...")

    stats = run_discovery_cycle(conn, profile, companies)
    conn.close()

    for job, score in stats["strong_matches"]:
        print(f"  -> Strong match ({score:.0f}): {job.title} at {job.company_name}")

    print(
        f"\nDone. Discovered: {stats['jobs_discovered']}, new: {stats['jobs_new']}, "
        f"scored: {stats['jobs_scored']}, resumes generated: {stats['resumes_generated']}"
    )


if __name__ == "__main__":
    main()
