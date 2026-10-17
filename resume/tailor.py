"""
Resume tailoring.

IMPORTANT: this module never invents skills, projects, or experience. It only
REORDERS and SELECTS from what's already in the user's profile/base resume,
putting the most relevant-to-this-job content first. This is a deliberate,
safety-driven design choice -- see config/profile.yaml's own warning that the
agent must never invent facts.

Relevance is computed by simple keyword overlap between the job description
and each skill/project, which is free, fast, and fully deterministic --
no AI call needed for this step.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from discovery.job_model import Job


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9+.#]*", text.lower()))


@dataclass
class TailoredResume:
    full_name: str
    contact_line: str
    summary: str
    ordered_skills: dict[str, list[str]]   # category -> skills, most relevant category order
    ordered_projects: list[dict]           # most relevant project first
    education: list[dict]
    certifications: list[str]
    languages: list[str]
    keywords_emphasized: list[str] = field(default_factory=list)


def _project_relevance(project: dict, job_tokens: set[str]) -> int:
    project_tokens = _tokenize(project.get("name", "") + " " + project.get("description", ""))
    project_tokens |= {t.lower() for t in project.get("tech_stack", [])}
    return len(project_tokens & job_tokens)


def _skill_category_relevance(skills: list[str], job_tokens: set[str]) -> int:
    skill_tokens = {s.lower() for s in skills}
    return len(skill_tokens & job_tokens)


def tailor_resume(job: Job, profile: dict) -> TailoredResume:
    """Pure function: given a Job and a profile dict, return a TailoredResume
    that reorders the user's real content by relevance to this job. Never
    adds content that isn't in the profile."""
    job_tokens = _tokenize(job.description + " " + job.title)

    personal = profile.get("personal", {})
    full_name = personal.get("full_name", "")
    contact_parts = [
        personal.get("email", ""),
        personal.get("phone", ""),
        personal.get("city", ""),
        personal.get("linkedin_url", ""),
        personal.get("github_url", ""),
        personal.get("portfolio_url", ""),
    ]
    contact_line = " | ".join(p for p in contact_parts if p)

    # Order skill categories by how relevant each is to this job
    skills = profile.get("skills", {})
    categories = ["programming_languages", "frameworks", "databases", "tools", "other"]
    scored_categories = [
        (cat, _skill_category_relevance(skills.get(cat, []) or [], job_tokens))
        for cat in categories
        if skills.get(cat)
    ]
    scored_categories.sort(key=lambda x: x[1], reverse=True)
    ordered_skills = {cat: skills[cat] for cat, _ in scored_categories}

    # Order projects by relevance, most relevant first -- never drop any
    projects = profile.get("projects", []) or []
    scored_projects = [(p, _project_relevance(p, job_tokens)) for p in projects]
    scored_projects.sort(key=lambda x: x[1], reverse=True)
    ordered_projects = [p for p, _score in scored_projects]

    # Keywords that appear in both the job and the user's real skills --
    # these are true, honest overlaps worth surfacing in the summary line.
    all_skill_tokens: set[str] = set()
    for cat_skills in skills.values():
        all_skill_tokens |= {s.lower() for s in (cat_skills or [])}
    keywords_emphasized = sorted(all_skill_tokens & job_tokens)[:8]

    summary = _build_summary(profile, job, keywords_emphasized)

    return TailoredResume(
        full_name=full_name,
        contact_line=contact_line,
        summary=summary,
        ordered_skills=ordered_skills,
        ordered_projects=ordered_projects,
        education=profile.get("education", []) or [],
        certifications=profile.get("certifications", []) or [],
        languages=profile.get("languages_spoken", []) or [],
        keywords_emphasized=keywords_emphasized,
    )


def _build_summary(profile: dict, job: Job, keywords: list[str]) -> str:
    role = profile.get("role", {})
    target_roles = role.get("target_roles", [])
    role_label = target_roles[0] if target_roles else "Software Engineer"
    experience_level = role.get("experience_level", "entry")

    if keywords:
        keyword_str = ", ".join(keywords[:5])
        return (
            f"{experience_level.capitalize()}-level {role_label} with hands-on experience in "
            f"{keyword_str}. Seeking the {job.title} role at {job.company_name}."
        )
    return (
        f"{experience_level.capitalize()}-level {role_label} seeking the {job.title} "
        f"role at {job.company_name}."
    )
