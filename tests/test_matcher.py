import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from discovery.job_model import Job
from ai.matcher import score_job


def make_profile(**overrides) -> dict:
    base = {
        "personal": {},
        "role": {"experience_level": "entry"},
        "skills": {
            "programming_languages": ["Python", "JavaScript"],
            "frameworks": ["Django", "React"],
            "databases": ["PostgreSQL"],
            "tools": ["Git", "Docker"],
            "other": [],
        },
        "location": {
            "preferred_locations": ["Mumbai", "Pune"],
            "remote_preference": "hybrid",
            "willing_to_relocate": False,
        },
        "compensation": {"expected_salary": 800000, "minimum_salary": 500000},
        "thresholds": {"job_match_threshold": 60},
    }
    base.update(overrides)
    return base


def test_strong_match_scores_high():
    profile = make_profile()
    job = Job(
        platform="greenhouse",
        company_name="Acme",
        title="Entry Level Python Developer",
        location="Mumbai",
        remote_type="hybrid",
        experience_level="entry",
        description="We need Python, Django and PostgreSQL skills. Git required.",
        salary_min=600000,
        salary_max=900000,
    )
    result = score_job(job, profile)
    assert result.overall_score > 70
    assert "python" in result.matched_skills


def test_weak_skill_match_scores_lower():
    profile = make_profile()
    job = Job(
        platform="greenhouse",
        company_name="Acme",
        title="Senior Java Architect",
        location="Mumbai",
        experience_level="senior",
        description="Java, Kubernetes, Scala expert needed.",
    )
    result = score_job(job, profile)
    assert result.skill_score < 30


def test_location_mismatch_without_relocation_scores_low():
    profile = make_profile()
    job = Job(
        platform="greenhouse",
        company_name="Acme",
        title="Python Developer",
        location="Berlin, Germany",
        remote_type="onsite",
        description="Python Django PostgreSQL",
    )
    result = score_job(job, profile)
    assert result.location_score <= 20


def test_remote_job_scores_well_on_location_regardless_of_city():
    profile = make_profile()
    job = Job(
        platform="greenhouse",
        company_name="Acme",
        title="Python Developer",
        location="Anywhere",
        remote_type="remote",
        description="Python Django",
    )
    result = score_job(job, profile)
    assert result.location_score == 100.0


def test_experience_gap_adds_disqualifier():
    profile = make_profile()
    job = Job(
        platform="greenhouse",
        company_name="Acme",
        title="Principal Engineer",
        experience_level="principal",
        description="Python",
    )
    result = score_job(job, profile)
    assert result.disqualifiers
    assert result.experience_score < 30


def test_salary_below_minimum_scores_low():
    profile = make_profile()
    job = Job(
        platform="greenhouse",
        company_name="Acme",
        title="Python Developer",
        description="Python",
        salary_min=200000,
        salary_max=300000,  # below minimum_salary of 500000
    )
    result = score_job(job, profile)
    assert result.salary_score <= 40


def test_missing_salary_data_does_not_punish():
    profile = make_profile()
    job = Job(
        platform="greenhouse",
        company_name="Acme",
        title="Python Developer",
        description="Python",
        # no salary fields set
    )
    result = score_job(job, profile)
    assert result.salary_score >= 60  # neutral, not punished for missing data


def test_result_serializes_to_dict():
    profile = make_profile()
    job = Job(platform="greenhouse", company_name="Acme", title="Python Developer",
               description="Python")
    result = score_job(job, profile)
    d = result.to_dict()
    assert "overall_score" in d
    assert isinstance(d["matched_skills"], list)
