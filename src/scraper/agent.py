"""Agent orchestration for the sepsis literature crawler."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Mapping

from .sepsis_project import LiteratureCrawler

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentConfig:
    """Configuration for running the crawler agent."""

    output_dir: Path = Path("data")
    queries: Mapping[str, str] | None = None
    max_articles: int = 50
    skip_citations: bool = False
    citation_root: Path | None = None

    def clone(self) -> "AgentConfig":
        return AgentConfig(
            output_dir=self.output_dir,
            queries=dict(self.queries) if self.queries is not None else None,
            max_articles=self.max_articles,
            skip_citations=self.skip_citations,
            citation_root=self.citation_root,
        )


@dataclass(slots=True)
class AgentError:
    """Capture a failure the agent encountered and any fix it applied."""

    attempt: int
    message: str
    fix_applied: str | None = None


@dataclass(slots=True)
class AgentResult:
    """Summary of the agent run including crawler metrics."""

    success: bool
    attempts: int
    report: Mapping[str, Dict[str, int]]
    notes: List[str] = field(default_factory=list)
    errors: List[AgentError] = field(default_factory=list)


class CrawlerAgent:
    """Coordinate crawler execution and automatically respond to failures."""

    def __init__(
        self,
        *,
        config: AgentConfig | None = None,
        max_attempts: int = 3,
        crawler_factory: Callable[..., LiteratureCrawler] | None = None,
    ) -> None:
        self.config = (config or AgentConfig()).clone()
        self.max_attempts = max(1, int(max_attempts))
        self.crawler_factory = crawler_factory or LiteratureCrawler

    def run(self) -> AgentResult:
        """Execute the crawler with self-healing retries when possible."""

        errors: List[AgentError] = []
        notes: List[str] = []
        report: Mapping[str, Dict[str, int]] = {}

        for attempt in range(1, self.max_attempts + 1):
            crawler = self._make_crawler()
            LOGGER.info("Agent attempt %s of %s", attempt, self.max_attempts)
            try:
                results = crawler.run()
                report = crawler.report
            except Exception as exc:  # pragma: no cover - defensive logging path
                fix = self._apply_fix(exc)
                errors.append(AgentError(attempt=attempt, message=str(exc), fix_applied=fix))
                LOGGER.warning("Agent attempt %s failed: %s", attempt, exc)
                if fix:
                    notes.append(f"Attempt {attempt}: {fix}")
                if attempt == self.max_attempts:
                    return AgentResult(
                        success=False,
                        attempts=attempt,
                        report=report,
                        notes=notes,
                        errors=errors,
                    )
                continue

            notes.extend(self._post_run_notes(results, report))
            return AgentResult(
                success=True,
                attempts=attempt,
                report=report,
                notes=notes,
                errors=errors,
            )

        return AgentResult(success=False, attempts=self.max_attempts, report=report, notes=notes, errors=errors)

    def _make_crawler(self) -> LiteratureCrawler:
        kwargs: Dict[str, object] = {
            "output_dir": self.config.output_dir,
            "queries": self.config.queries,
            "max_articles": self.config.max_articles,
            "skip_citations": self.config.skip_citations,
        }
        if self.config.citation_root is not None:
            kwargs["citation_root"] = self.config.citation_root
        return self.crawler_factory(**kwargs)

    def _apply_fix(self, exc: Exception) -> str | None:
        message = str(exc)
        lowered = message.lower()

        if "citation" in lowered and not self.config.skip_citations:
            self.config.skip_citations = True
            return "Enabled skip_citations after citation failure"

        if ("failed to fetch data" in lowered or "timeout" in lowered) and self.config.max_articles > 10:
            new_limit = max(10, self.config.max_articles // 2)
            if new_limit != self.config.max_articles:
                self.config.max_articles = new_limit
                return f"Reduced max_articles to {new_limit} after fetch failure"

        return None

    def _post_run_notes(
        self,
        results: Mapping[str, List[object]],
        report: Mapping[str, Dict[str, int]],
    ) -> List[str]:
        notes: List[str] = []
        for name, articles in results.items():
            if not articles:
                notes.append(
                    f"Query '{name}' returned no articles. Consider refining the search string."
                )

        for name, metrics in report.items():
            if metrics.get("missing_pmids", 0) > 0:
                notes.append(
                    f"Query '{name}' has {metrics['missing_pmids']} articles without PMIDs; citations cannot be saved."
                )
            if metrics.get("citations_saved", 0) == 0 and not self.config.skip_citations:
                notes.append(
                    f"Query '{name}' saved no citations. Check network access or rerun with --skip-citations if needed."
                )
        return notes


__all__ = [
    "AgentConfig",
    "AgentError",
    "AgentResult",
    "CrawlerAgent",
]
