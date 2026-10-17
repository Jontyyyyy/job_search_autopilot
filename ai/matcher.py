"""
Job matching engine.

Produces a 0-100 score for how well a job fits the user's profile, broken
into explainable sub-scores (skills, experience, location, salary) so the
dashboard and the daily report can show *why* a job scored the way it did,
not just a bare number.

This module is deliberately rule-based and dependency-free (no AI call
required) so it's fast, free, deterministic, and testable without mocking an
LLM. The AI layer (ai/provider.py, built in a later module) is used
separately for things rules can't do well: rewriting resume text, writing
cover notes, classifying emails.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from discovery.job_model import Job


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9+.#]*", text.lower()))


@dataclass
class MatchResult:
    overall_score: float
    skill_score: float
    experience_score: float
    location_score: float
    salary_score: float
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    disqualifiers: list[str] = field(default_factory=list)
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "overall_score": round(self.overall_score, 1),
            "skill_score": round(self.skill_score, 1),
            "experience_score": round(self.experience_score, 1),
            "location_score": round(self.location_score, 1),
            "salary_score": round(self.salary_score, 1),
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "disqualifiers": self.disqualifiers,
            "reasoning": self.reasoning,
        }


# Component weights -- must sum to 1.0
WEIGHTS = {
    "skill": 0.45,
    "experience": 0.20,
    "location": 0.20,
    "salary": 0.15,
}

EXPERIENCE_LEVEL_ORDER = ["intern", "entry", "junior", "mid", "senior", "lead", "principal"]


def _profile_skills(profile: dict) -> set[str]:
    skills = profile.get("skills", {})
    all_skills: list[str] = []
    for key in ("programming_languages", "frameworks", "databases", "tools", "other"):
        all_skills.extend(skills.get(key, []) or [])
    return {s.lower().strip() for s in all_skills if s}


TARGET_SKILL_MATCHES = 5  # matching this many relevant skills already earns a full 100%


def _score_skills(job: Job, profile_skill_set: set[str]) -> tuple[float, list[str], list[str]]:
    job_text_tokens = _tokenize(job.description + " " + job.title)
    job_skill_tokens = {s.lower().strip() for s in job.skills if s} | job_text_tokens

    if not profile_skill_set:
        return 0.0, [], []

    matched = sorted(s for s in profile_skill_set if s in job_skill_tokens)
    missing_from_profile = sorted(
        s for s in job_skill_tokens
        if s in profile_skill_set - set(matched)
    )
    score = 100.0 * min(1.0, len(matched) / TARGET_SKILL_MATCHES)
    return score, matched, missing_from_profile


def _score_experience(job: Job, profile: dict) -> tuple[float, list[str]]:
    disqualifiers: list[str] = []
    job_level = (job.experience_level or "").lower().strip()
    profile_level = (profile.get("role", {}).get("experience_level") or "").lower().strip()

    if not job_level or not profile_level:
        return 70.0, disqualifiers  # unknown -> neutral-ish score, don't punish

    try:
        job_idx = EXPERIENCE_LEVEL_ORDER.index(job_level)
        profile_idx = EXPERIENCE_LEVEL_ORDER.index(profile_level)
    except ValueError:
        return 70.0, disqualifiers

    diff = job_idx - profile_idx
    if diff == 0:
        return 100.0, disqualifiers
    if diff == 1:
        return 75.0, disqualifiers       # job wants one level above -- a stretch, still worth showing
    if diff == -1:
        return 85.0, disqualifiers       # job is one level below -- fine, slightly overqualified
    if diff >= 2:
        disqualifiers.append(
            f"Job requires '{job_level}' level, well above your '{profile_level}' level."
        )
        return 20.0, disqualifiers
    return 60.0, disqualifiers           # significantly overqualified


def _score_location(job: Job, profile: dict) -> float:
    location_cfg = profile.get("location", {})
    preferred = [p.lower().strip() for p in location_cfg.get("preferred_locations", [])]
    remote_pref = (location_cfg.get("remote_preference") or "any").lower()
    willing_to_relocate = bool(location_cfg.get("willing_to_relocate", False))

    job_remote = (job.remote_type or "").lower()
    job_location = (job.location or "").lower()

    if remote_pref == "any":
        return 100.0

    if job_remote == "remote":
        return 100.0 if remote_pref in ("remote", "hybrid", "any") else 70.0

    if preferred and any(p in job_location for p in preferred):
        return 100.0

    if willing_to_relocate:
        return 60.0

    if not preferred:
        return 70.0  # no preference configured -- don't penalize

    return 20.0


def _score_salary(job: Job, profile: dict) -> float:
    comp = profile.get("compensation", {})
    expected = comp.get("expected_salary") or 0
    minimum = comp.get("minimum_salary") or 0

    if not minimum or not job.salary_max:
        return 70.0  # not enough data to judge -- neutral, don't punish

    if job.salary_max >= expected:
        return 100.0
    if job.salary_max >= minimum:
        # Linear interpolation between minimum (60) and expected (100)
        span = max(expected - minimum, 1)
        return 60.0 + 40.0 * ((job.salary_max - minimum) / span)
    return 30.0


def score_job(job: Job, profile: dict) -> MatchResult:
    """Pure function: given a Job and a profile dict, return a MatchResult."""
    profile_skill_set = _profile_skills(profile)

    skill_score, matched, missing = _score_skills(job, profile_skill_set)
    experience_score, exp_disqualifiers = _score_experience(job, profile)
    location_score = _score_location(job, profile)
    salary_score = _score_salary(job, profile)

    overall = (
        skill_score * WEIGHTS["skill"]
        + experience_score * WEIGHTS["experience"]
        + location_score * WEIGHTS["location"]
        + salary_score * WEIGHTS["salary"]
    )

    reasoning = (
        f"Skill match {skill_score:.0f}% ({len(matched)} matched), "
        f"experience fit {experience_score:.0f}%, "
        f"location fit {location_score:.0f}%, "
        f"salary fit {salary_score:.0f}%."
    )

    return MatchResult(
        overall_score=overall,
        skill_score=skill_score,
        experience_score=experience_score,
        location_score=location_score,
        salary_score=salary_score,
        matched_skills=matched,
        missing_skills=missing[:10],  # cap noise
        disqualifiers=exp_disqualifiers,
        reasoning=reasoning,
    )