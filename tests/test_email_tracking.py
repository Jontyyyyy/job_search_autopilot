import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from email_tracking.classifier import classify_email
from email_tracking.parser import parse_raw_email


# ---------- classifier tests ----------

def test_classifies_clear_rejection():
    result = classify_email(
        subject="Update on your application",
        body="Unfortunately, we have decided to move forward with other candidates at this time.",
    )
    assert result.category == "rejection"
    assert result.confidence > 0


def test_classifies_interview_invitation():
    result = classify_email(
        subject="Interview invitation - Backend Developer",
        body="We would like to invite you to interview for the role. Please schedule a call at your convenience.",
    )
    assert result.category == "interview"


def test_classifies_assessment():
    result = classify_email(
        subject="Next step: Online Assessment",
        body="Please complete the following coding assessment on HackerRank within 48 hours.",
    )
    assert result.category == "assessment"


def test_classifies_shortlist():
    result = classify_email(
        subject="Great news!",
        body="We are pleased to inform you that you have been shortlisted for the next round.",
    )
    assert result.category == "shortlisted"


def test_classifies_application_confirmation():
    result = classify_email(
        subject="Application Received",
        body="Thank you for applying. We have received your application and will review it shortly.",
    )
    assert result.category == "application_confirmation"


def test_classifies_recruiter_outreach():
    result = classify_email(
        subject="Opportunity at Acme Corp",
        body="Hi, I came across your profile and think you'd be a great fit. I'm a recruiter at Acme.",
    )
    assert result.category == "recruiter_message"


def test_unrelated_email_classified_as_other():
    result = classify_email(
        subject="Your Amazon order has shipped",
        body="Your package is on its way and will arrive tomorrow.",
    )
    assert result.category == "other"
    assert result.confidence == 0.0


def test_rejection_takes_priority_over_interview_mention():
    # Tricky case: mentions "interview" but is clearly a rejection --
    # rejection keywords must win since this priority matters more
    result = classify_email(
        subject="Interview process update",
        body="Unfortunately, we have decided not to move forward with your application after the interview process.",
    )
    assert result.category == "rejection"


def test_confidence_increases_with_more_keyword_matches():
    weak = classify_email(subject="", body="shortlisted")
    strong = classify_email(
        subject="",
        body="You have been shortlisted and selected for the next stage, moved to the next round.",
    )
    assert strong.confidence >= weak.confidence


def test_classify_never_raises_on_empty_input():
    result = classify_email(subject="", body="")
    assert result.category == "other"


def test_classify_handles_none_gracefully():
    result = classify_email(subject=None, body=None)
    assert result.category == "other"


# ---------- parser tests ----------

def test_parse_simple_plain_text_email():
    raw = (
        b"From: recruiter@acme.com\r\n"
        b"Subject: Interview Invitation\r\n"
        b"Date: Mon, 1 Jan 2026 10:00:00 +0000\r\n"
        b"Message-ID: <abc123@acme.com>\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"We would like to invite you to interview.\r\n"
    )
    parsed = parse_raw_email(raw)
    assert parsed.sender == "recruiter@acme.com"
    assert parsed.subject == "Interview Invitation"
    assert "invite you to interview" in parsed.body
    assert parsed.message_id == "<abc123@acme.com>"


def test_parse_html_email_strips_tags():
    raw = (
        b"From: recruiter@acme.com\r\n"
        b"Subject: Update\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"\r\n"
        b"<html><body><p>Hello <b>there</b>, unfortunately we regret to inform you.</p></body></html>\r\n"
    )
    parsed = parse_raw_email(raw)
    assert "<p>" not in parsed.body
    assert "<b>" not in parsed.body
    assert "Hello there" in parsed.body
    assert "regret to inform" in parsed.body


def test_parse_malformed_email_does_not_raise():
    raw = b"this is not a valid email at all, just garbage bytes \xff\xfe"
    parsed = parse_raw_email(raw)
    # Must not raise -- degrades gracefully
    assert parsed is not None


def test_parse_missing_headers_returns_empty_strings_not_none():
    raw = b"\r\n\r\nJust a body with no headers at all.\r\n"
    parsed = parse_raw_email(raw)
    assert parsed.sender == ""
    assert parsed.subject == ""
