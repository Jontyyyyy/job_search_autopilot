"""
Common interface every platform adapter implements, so the orchestrator
never needs to know which site a job came from.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from discovery.job_model import Job


class PlatformAdapter(ABC):
    platform_name: str = "unknown"

    @abstractmethod
    def discover_jobs(self, **kwargs) -> list[Job]:
        """Return a list of normalized Job objects. Must not raise on a
        single bad record -- skip and continue, only raise on total
        failure to reach the source."""
        raise NotImplementedError

    def capabilities(self) -> dict:
        """Describe what this adapter can legitimately do, so the decision
        engine can pick the strongest available method per platform."""
        return {
            "discovery": True,
            "application": False,
            "requires_browser": False,
            "requires_login": False,
        }
