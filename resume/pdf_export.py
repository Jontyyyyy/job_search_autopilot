"""
Exports a TailoredResume to a clean, single-column, ATS-friendly PDF using
ReportLab -- free, local, no API calls, no fonts/graphics that confuse
applicant tracking systems.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem

from resume.tailor import TailoredResume

CATEGORY_LABELS = {
    "programming_languages": "Languages",
    "frameworks": "Frameworks",
    "databases": "Databases",
    "tools": "Tools",
    "other": "Other",
}


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ResumeName", fontSize=16, leading=19, spaceAfter=2,
        fontName="Helvetica-Bold", alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="ResumeContact", fontSize=8.5, leading=11, spaceAfter=8,
        textColor="#444444", alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader", fontSize=11, leading=14, spaceBefore=8, spaceAfter=3,
        fontName="Helvetica-Bold", textColor="#1a1a1a",
    ))
    styles.add(ParagraphStyle(
        name="ResumeBody", fontSize=9, leading=12, spaceAfter=3,
    ))
    return styles


def export_resume_pdf(resume: TailoredResume, output_path: str) -> str:
    """Writes the PDF to output_path and returns that path."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    styles = _build_styles()

    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        leftMargin=0.65 * inch, rightMargin=0.65 * inch,
        topMargin=0.45 * inch, bottomMargin=0.45 * inch,
    )

    story = []
    story.append(Paragraph(resume.full_name, styles["ResumeName"]))
    story.append(Paragraph(resume.contact_line, styles["ResumeContact"]))

    story.append(Paragraph("Summary", styles["SectionHeader"]))
    story.append(Paragraph(resume.summary, styles["ResumeBody"]))

    if resume.ordered_skills:
        story.append(Paragraph("Skills", styles["SectionHeader"]))
        for category, skills in resume.ordered_skills.items():
            label = CATEGORY_LABELS.get(category, category.replace("_", " ").title())
            story.append(Paragraph(f"<b>{label}:</b> {', '.join(skills)}", styles["ResumeBody"]))

    if resume.ordered_projects:
        story.append(Paragraph("Projects", styles["SectionHeader"]))
        for project in resume.ordered_projects:
            name = project.get("name", "")
            url = project.get("url", "")
            title_line = f"<b>{name}</b>" + (f" — {url}" if url else "")
            story.append(Paragraph(title_line, styles["ResumeBody"]))
            description = project.get("description", "")
            if description:
                story.append(Paragraph(description, styles["ResumeBody"]))
            tech_stack = project.get("tech_stack", [])
            if tech_stack:
                story.append(Paragraph(f"<i>Tech: {', '.join(tech_stack)}</i>", styles["ResumeBody"]))
            story.append(Spacer(1, 3))

    if resume.education:
        story.append(Paragraph("Education", styles["SectionHeader"]))
        for edu in resume.education:
            degree = edu.get("degree", "")
            institution = edu.get("institution", "")
            year = edu.get("year", "")
            grade = edu.get("grade", "")
            parts = [p for p in [degree, institution, str(year) if year else "", grade] if p]
            story.append(Paragraph(" — ".join(parts), styles["ResumeBody"]))

    if resume.certifications:
        story.append(Paragraph("Certifications", styles["SectionHeader"]))
        for cert in resume.certifications:
            story.append(Paragraph(f"• {cert}", styles["ResumeBody"]))

    if resume.languages:
        story.append(Paragraph("Languages", styles["SectionHeader"]))
        story.append(Paragraph(", ".join(resume.languages), styles["ResumeBody"]))

    doc.build(story)
    return output_path
