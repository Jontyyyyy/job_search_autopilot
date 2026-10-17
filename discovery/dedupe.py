"""
Job deduplication.

Two layers:
1. Exact match on job_id (same platform+external_id, or identical
   normalized company/title/location) -> same job, trivially.
2. Fuzzy cross-platform match: the same role posted on LinkedIn, Naukri AND
   the company's own Greenhouse board should collapse into ONE opportunity,
   with every source link preserved in job_sources.
"""
from __future__ import annotations

from dataclasses import dataclass

from discovery.job_model import Job

try:
    from rapidfuzz import fuzz

    def _similarity(a: str, b: str) -> float:
        return fuzz.token_sort_ratio(a, b)
except ImportError:  # graceful fallback with zero external dependencies
    from difflib import SequenceMatcher

    def _similarity(a: str, b: str) -> float:
        """
        Mimics rapidfuzz's token_sort_ratio: sort each string's words
        alphabetically before comparing, so word reordering ("Backend
        Engineer Senior" vs "Senior Backend Engineer") doesn't tank the
        score the way raw SequenceMatcher would.
        """
        a_sorted = " ".join(sorted(a.split()))
        b_sorted = " ".join(sorted(b.split()))
        return SequenceMatcher(None, a_sorted, b_sorted).ratio() * 100

FUZZY_THRESHOLD = 90  # 0-100


@dataclass
class DedupeResult:
    is_duplicate: bool
    matched_job_id: str | None
    confidence: float
    reason: str


class Deduplicator:
    """
    Holds an in-memory index of already-known jobs (job_id -> canonical
    signature) for a single discovery run, then checks new candidates
    against it. The caller is responsible for loading existing job_ids /
    signatures from the database before a run, and persisting new ones.
    """

    def __init__(self) -> None:
        self._known_ids: set[str] = set()
        self._known_signatures: dict[str, str] = {}  # job_id -> signature

    def load_existing(self, existing: list[tuple[str, str]]) -> None:
        """existing: list of (job_id, canonical_signature) from the DB."""
        for job_id, signature in existing:
            self._known_ids.add(job_id)
            self._known_signatures[job_id] = signature

    def check(self, job: Job) -> DedupeResult:
        if job.job_id in self._known_ids:
            return DedupeResult(True, job.job_id, 100.0, "exact_id_match")

        signature = job.canonical_signature()
        best_match_id = None
        best_score = 0.0
        for known_id, known_sig in self._known_signatures.items():
            score = _similarity(signature, known_sig)
            if score > best_score:
                best_score = score
                best_match_id = known_id

        if best_score >= FUZZY_THRESHOLD:
            return DedupeResult(True, best_match_id, best_score, "fuzzy_cross_platform_match")

        return DedupeResult(False, None, best_score, "unique")

    def register(self, job: Job) -> None:
        self._known_ids.add(job.job_id)
        self._known_signatures[job.job_id] = job.canonical_signature()
