import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from discovery.job_model import Job
from resume.tailor import tailor_resume
from resume.naming import resume_filename
from resume.pdf_export import export_resume_pdf


def make_profile() -> dict:
    return {
        "personal": {
            "full_name": "Test User",
            "email": "test@example.com",
            "phone": "+91-9999999999",
            "city": "Mumbai",
            "linkedin_url": "linkedin.com/in/testuser",
            "github_url": "",
            "portfolio_url": "",
        },
        "role": {"target_roles": ["Software Engineer"], "experience_level": "entry"},
        "skills": {
            "programming_languages": ["Python", "JavaScript"],
            "frameworks": ["Django", "React"],
            "databases": ["PostgreSQL"],
            "tools": ["Git"],
            "other": [],
        },
        "projects": [
            {
                "name": "Chat App",
                "description": "Real-time chat with Socket.IO",
                "tech_stack": ["React", "Node.js", "Socket.IO"],
                "url": "chatapp.example.com",
            },
            {
                "name": "Library System",
                "description": "Book management with Python and MySQL",
                "tech_stack": ["Python", "MySQL"],
                "url": "",
            },
        ],
        "education": [
            {"degree": "BCA", "institution": "Test College", "year": 2025, "grade": "65%"}
        ],
        "certifications": [],
        "languages_spoken": ["English"],
    }


def test_tailor_never_invents_skills():
    profile = make_profile()
    job = Job(platform="greenhouse", company_name="Acme", title="Python Developer",
               description="Need Python and Django experience.")
    resume = tailor_resume(job, profile)

    all_resume_skills = set()
    for skills in resume.ordered_skills.values():
        all_resume_skills.update(skills)
    all_profile_skills = set()
    for skills in profile["skills"].values():
        all_profile_skills.update(skills)

    # Every skill in the tailored resume must come from the profile -- no invention
    assert all_resume_skills <= all_profile_skills
    assert all_resume_skills == all_profile_skills  # none dropped either


def test_tailor_reorders_projects_by_relevance():
    profile = make_profile()
    job = Job(platform="greenhouse", company_name="Acme", title="Backend Developer",
               description="Python MySQL backend developer needed for library systems.")
    resume = tailor_resume(job, profile)

    # Library System should rank above Chat App for this Python/MySQL job
    assert resume.ordered_projects[0]["name"] == "Library System"


def test_tailor_reorders_skill_categories_by_relevance():
    profile = make_profile()
    job = Job(platform="greenhouse", company_name="Acme", title="React Developer",
               description="React frontend developer, must know React and JavaScript well.")
    resume = tailor_resume(job, profile)

    # frameworks (React) or programming_languages (JavaScript) should be prioritized
    first_category = list(resume.ordered_skills.keys())[0]
    assert first_category in ("frameworks", "programming_languages")


def test_tailor_summary_mentions_job_title_and_company():
    profile = make_profile()
    job = Job(platform="greenhouse", company_name="Acme Corp", title="Python Developer",
               description="Python developer role.")
    resume = tailor_resume(job, profile)
    assert "Python Developer" in resume.summary
    assert "Acme Corp" in resume.summary


def test_tailor_keeps_all_education_and_certifications():
    profile = make_profile()
    job = Job(platform="greenhouse", company_name="Acme", title="Developer", description="")
    resume = tailor_resume(job, profile)
    assert resume.education == profile["education"]
    assert resume.certifications == profile["certifications"]


def test_resume_filename_format():
    job = Job(platform="greenhouse", company_name="Acme Corp!", title="Senior Python Dev",
               external_id="1")
    filename = resume_filename(job, extension="pdf", on_date=date(2026, 1, 15))
    assert filename == "acme_corp_senior_python_dev_2026-01-15.pdf"


def test_resume_filename_handles_empty_strings():
    job = Job(platform="greenhouse", company_name="", title="", external_id="1")
    filename = resume_filename(job, on_date=date(2026, 1, 1))
    assert filename == "unknown_unknown_2026-01-01.pdf"


def test_pdf_export_creates_real_file(tmp_path):
    profile = make_profile()
    job = Job(platform="greenhouse", company_name="Acme", title="Python Developer",
               description="Need Python and Django experience.")
    resume = tailor_resume(job, profile)

    output_path = str(tmp_path / "test_resume.pdf")
    result_path = export_resume_pdf(resume, output_path)

    assert result_path == output_path
    assert Path(output_path).exists()
    assert Path(output_path).stat().st_size > 0  # not an empty/corrupt file

    # A real PDF starts with this magic header
    with open(output_path, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-"
