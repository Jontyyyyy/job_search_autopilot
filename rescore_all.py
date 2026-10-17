import json
import sqlite3

from discovery.job_model import Job
from ai.matcher import score_job
from database.repository import save_job
from utils.config_loader import load_profile

profile = load_profile()
conn = sqlite3.connect("data/job_autopilot.db")
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT * FROM jobs").fetchall()
count = 0

for row in rows:
    job = Job(
        platform=row["platform"],
        company_name=row["company_name"],
        title=row["title"],
        external_id=row["external_id"],
        location=row["location"] or "",
        remote_type=row["remote_type"] or "",
        salary_min=row["salary_min"],
        salary_max=row["salary_max"],
        currency=row["currency"] or "",
        employment_type=row["employment_type"] or "",
        experience_level=row["experience_level"] or "",
        description=row["description"] or "",
        skills=json.loads(row["skills"]) if row["skills"] else [],
        posting_date=row["posting_date"] or "",
        source=row["source"] or "",
        ats_type=row["ats_type"] or "",
        job_url=row["job_url"] or "",
        apply_url=row["apply_url"] or "",
    )
    match = score_job(job, profile)
    save_job(conn, job, match)
    count += 1

conn.close()
print(f"Rescored {count} jobs with the current matcher.")