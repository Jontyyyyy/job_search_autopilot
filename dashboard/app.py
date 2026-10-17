"""
The command center. Run with: streamlit run dashboard/app.py

All data here comes from database/repository.py, which is the single
source of truth every other module writes into. This file only reads and
displays -- it never mutates state outside of the approve/skip buttons,
which call repository functions directly.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.repository import (
    list_jobs, list_applications, list_emails, get_today_stats, get_pipeline_counts,
    update_application_state,
)
from utils.config_loader import load_settings

st.set_page_config(page_title="Job Search Autopilot", page_icon="🧭", layout="wide")


@st.cache_resource
def get_connection() -> sqlite3.Connection:
    settings = load_settings()
    db_path = settings.get("database", {}).get("path", "data/job_autopilot.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def page_today(conn: sqlite3.Connection) -> None:
    st.header("Today")
    stats = get_today_stats(conn)

    cols = st.columns(4)
    cols[0].metric("Jobs discovered", stats["jobs_discovered"])
    cols[1].metric("Jobs scored", stats["jobs_scored"])
    cols[2].metric("Resumes generated", stats["resumes_generated"])
    cols[3].metric("Applications submitted", stats["applications_submitted"])

    cols2 = st.columns(4)
    cols2[0].metric("⭐ Shortlists", stats["shortlists"])
    cols2[1].metric("🎤 Interviews", stats["interviews"])
    cols2[2].metric("❌ Rejections", stats["rejections"])
    cols2[3].metric("⚠️ Pending your action", stats["pending_actions"])

    st.subheader("Recently discovered jobs")
    jobs = list_jobs(conn, limit=10)
    if jobs:
        df = _df(jobs)[["discovered_at", "company_name", "title", "platform", "match_score", "status"]]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No jobs discovered yet. Run the discovery adapters to populate this.")


def page_pipeline(conn: sqlite3.Connection) -> None:
    st.header("Pipeline")
    counts = get_pipeline_counts(conn)

    stages = ["DISCOVERED", "MATCHED", "RESUME_READY", "APPLICATION_READY",
               "PENDING_APPROVAL", "SUBMITTED", "SHORTLISTED", "INTERVIEW", "REJECTED"]
    cols = st.columns(len(stages))
    for col, stage in zip(cols, stages):
        col.metric(stage.replace("_", " ").title(), counts.get(stage, 0))

    st.subheader("All jobs by status")
    jobs = list_jobs(conn, limit=500)
    if jobs:
        df = _df(jobs)[["title", "company_name", "platform", "status", "match_score"]]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No jobs yet.")


def page_jobs(conn: sqlite3.Connection) -> None:
    st.header("Jobs")
    jobs = list_jobs(conn, limit=500)
    if not jobs:
        st.info("No jobs yet. Run discovery to populate this.")
        return

    df = _df(jobs)

    col1, col2, col3 = st.columns(3)
    platform_filter = col1.multiselect("Platform", sorted(df["platform"].unique()))
    status_filter = col2.multiselect("Status", sorted(df["status"].unique()))
    min_score = col3.slider("Minimum match score", 0, 100, 0)

    filtered = df.copy()
    if platform_filter:
        filtered = filtered[filtered["platform"].isin(platform_filter)]
    if status_filter:
        filtered = filtered[filtered["status"].isin(status_filter)]
    filtered = filtered[filtered["match_score"].fillna(0) >= min_score]

    st.dataframe(
        filtered[["title", "company_name", "platform", "location", "match_score", "status", "job_url"]],
        use_container_width=True, hide_index=True,
    )


def page_applications(conn: sqlite3.Connection) -> None:
    st.header("Applications")
    apps = list_applications(conn, limit=500)
    if not apps:
        st.info("No applications yet.")
        return

    df = _df(apps)
    st.dataframe(
        df[["title", "company_name", "job_platform", "state", "autonomy_level", "updated_at"]],
        use_container_width=True, hide_index=True,
    )


def page_emails(conn: sqlite3.Connection) -> None:
    st.header("Emails")
    classification_filter = st.selectbox(
        "Filter by type", ["All", "shortlisted", "interview", "assessment",
                             "rejection", "recruiter_message", "application_confirmation", "other"],
    )
    emails = list_emails(
        conn, classification=None if classification_filter == "All" else classification_filter, limit=200,
    )
    if not emails:
        st.info("No emails tracked yet.")
        return

    df = _df(emails)
    st.dataframe(
        df[["received_at", "sender", "subject", "classification", "confidence"]],
        use_container_width=True, hide_index=True,
    )


def page_pending_actions(conn: sqlite3.Connection) -> None:
    st.header("Pending Actions")
    apps = list_applications(conn, limit=500)
    pending = [a for a in apps if a["state"] == "ACTION_REQUIRED"]

    if not pending:
        st.success("Nothing waiting on you right now.")
        return

    for app in pending:
        with st.container(border=True):
            st.write(f"**{app['title']}** at **{app['company_name']}** ({app['job_platform']})")
            st.caption(app.get("notes", "No details recorded."))
            col1, col2 = st.columns(2)
            if col1.button("Mark resolved", key=f"resolve_{app['application_id']}"):
                update_application_state(conn, app["application_id"], "APPLICATION_READY")
                st.rerun()
            if col2.button("Skip this job", key=f"skip_{app['application_id']}"):
                update_application_state(conn, app["application_id"], "SKIPPED")
                st.rerun()


def main() -> None:
    conn = get_connection()
    st.sidebar.title("🧭 Job Search Autopilot")
    page = st.sidebar.radio(
        "Navigate", ["Today", "Pipeline", "Jobs", "Applications", "Emails", "Pending Actions"],
    )

    if page == "Today":
        page_today(conn)
    elif page == "Pipeline":
        page_pipeline(conn)
    elif page == "Jobs":
        page_jobs(conn)
    elif page == "Applications":
        page_applications(conn)
    elif page == "Emails":
        page_emails(conn)
    elif page == "Pending Actions":
        page_pending_actions(conn)


if __name__ == "__main__":
    main()
