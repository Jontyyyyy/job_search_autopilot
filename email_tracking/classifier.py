"""
Classifies an email as shortlisted / interview / assessment / rejection /
recruiter message / application confirmation / other, using keyword rules.

Rule-based and free -- no AI call needed for the common cases. This keeps
classification fast, deterministic, and testable. A later module can add an
AI fallback for ambiguous cases the keyword rules don't confidently resolve.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Order matters: more specific / higher-priority categories are checked
# first, so an email that mentions both "interview" and "unfortunately"
# (e.g. "unfortunately the interview slot is full") doesn't get
# misclassified -- rejection keywords are checked first since getting a
# false positive shortlist/interview alert wrong is worse than being
# cautious.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "rejection": [
        "unfortunately", "not moving forward", "not selected", "will not be proceeding",
        "decided to move forward with other", "regret to inform", "not a match at this time",
        "pursue other candidates", "will not be moving forward", "thank you for your interest",
        "have chosen another candidate", "position has been filled",
    ],
    "interview": [
        "interview invitation", "schedule an interview", "would like to interview",
        "interview with", "video call", "phone screen", "technical interview",
        "schedule a call", "invite you to interview", "interview process",
        "available for a call", "book a slot", "calendly",
    ],
    "assessment": [
        "coding assessment", "online assessment", "take-home assignment", "take home test",
        "hackerrank", "codility", "complete the assessment", "technical test",
        "please complete the following", "assignment due",
    ],
    "shortlisted": [
        "shortlisted", "shortlist", "moved to the next round", "next round",
        "pleased to inform", "selected for the next stage", "advance to the next",
    ],
    "application_confirmation": [
        "application received", "thank you for applying", "we have received your application",
        "application has been submitted", "confirm receipt of your application",
    ],
    "recruiter_message": [
        "reaching out", "came across your profile", "opportunity that might interest you",
        "recruiter", "talent acquisition", "hiring manager",
    ],
}

# Checked in this priority order -- first category with any keyword match wins.
PRIORITY_ORDER = [
    "rejection", "interview", "assessment", "shortlisted",
    "application_confirmation", "recruiter_message",
]


@dataclass
class EmailClassification:
    category: str              # one of CATEGORY_KEYWORDS keys, or "other"
    confidence: float          # 0.0-1.0, based on number of keyword matches
    matched_keywords: list[str] = field(default_factory=list)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def classify_email(subject: str, body: str) -> EmailClassification:
    """Pure function: classify an email from its subject and body text.
    Never raises; always returns a classification, falling back to "other"
    with 0 confidence when nothing matches."""
    combined = _normalize((subject or "") + " " + (body or ""))

    for category in PRIORITY_ORDER:
        keywords = CATEGORY_KEYWORDS[category]
        matched = [kw for kw in keywords if kw in combined]
        if matched:
            # confidence scales with how many distinct keywords matched,
            # capped at 1.0 -- 1 match is a solid signal already, 3+ is
            # very high confidence
            confidence = min(1.0, 0.6 + 0.15 * (len(matched) - 1))
            return EmailClassification(category=category, confidence=confidence, matched_keywords=matched)

    return EmailClassification(category="other", confidence=0.0, matched_keywords=[])
