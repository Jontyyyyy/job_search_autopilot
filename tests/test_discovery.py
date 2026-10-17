import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from discovery.job_model import Job
from discovery.dedupe import Deduplicator


def test_job_id_stable_for_same_external_id():
    j1 = Job(platform="greenhouse", company_name="Acme", title="Backend Engineer",
              external_id="gh-123")
    j2 = Job(platform="greenhouse", company_name="Acme", title="Backend Engineer",
              external_id="gh-123")
    assert j1.job_id == j2.job_id


def test_job_id_differs_for_different_companies():
    j1 = Job(platform="linkedin", company_name="Acme", title="Backend Engineer")
    j2 = Job(platform="linkedin", company_name="Globex", title="Backend Engineer")
    assert j1.job_id != j2.job_id


def test_job_id_same_for_identical_text_no_external_id():
    j1 = Job(platform="linkedin", company_name="Acme Corp", title="Backend Engineer",
              location="Mumbai")
    j2 = Job(platform="linkedin", company_name="Acme Corp", title="Backend Engineer",
              location="Mumbai")
    assert j1.job_id == j2.job_id


def test_required_fields_present():
    assert Job.required_fields_present({"platform": "x", "company_name": "y", "title": "z"})
    assert not Job.required_fields_present({"platform": "x", "company_name": "y"})


def test_dedupe_exact_match():
    dedupe = Deduplicator()
    j1 = Job(platform="greenhouse", company_name="Acme", title="Backend Engineer",
              external_id="gh-1")
    dedupe.register(j1)

    j2 = Job(platform="greenhouse", company_name="Acme", title="Backend Engineer",
              external_id="gh-1")
    result = dedupe.check(j2)
    assert result.is_duplicate
    assert result.reason == "exact_id_match"


def test_dedupe_cross_platform_fuzzy_match():
    dedupe = Deduplicator()
    linkedin_job = Job(platform="linkedin", company_name="Acme Corp",
                         title="Senior Backend Engineer", location="Mumbai")
    dedupe.register(linkedin_job)

    # Same role, scraped from the company's own career page: location has
    # an extra "India" suffix, which survives punctuation normalization and
    # keeps word order intact -- must NOT get the same job_id (so this only
    # matches via the fuzzy signature comparison), but is still clearly the
    # same real-world opportunity.
    greenhouse_job = Job(platform="greenhouse", company_name="Acme Corp",
                           title="Senior Backend Engineer", location="Mumbai India")
    assert greenhouse_job.job_id != linkedin_job.job_id  # sanity: not an exact-id match
    result = dedupe.check(greenhouse_job)
    assert result.is_duplicate
    assert result.reason == "fuzzy_cross_platform_match"


def test_dedupe_distinct_jobs_not_merged():
    dedupe = Deduplicator()
    j1 = Job(platform="linkedin", company_name="Acme Corp", title="Backend Engineer",
              location="Mumbai")
    dedupe.register(j1)

    j2 = Job(platform="linkedin", company_name="Globex Inc", title="Frontend Engineer",
              location="Pune")
    result = dedupe.check(j2)
    assert not result.is_duplicate


def test_job_to_dict_serializes_skills_as_json():
    j = Job(platform="linkedin", company_name="Acme", title="Engineer",
             skills=["Python", "Django"])
    d = j.to_dict()
    assert isinstance(d["skills"], str)
    assert "Python" in d["skills"]
