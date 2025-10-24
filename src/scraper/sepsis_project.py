"""High level pipeline for collecting literature on serum TDP-43 and sepsis brain injury."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .pubmed import Article, crawl_pubmed_articles, fetch_endnote_citation

LOGGER = logging.getLogger(__name__)

DEFAULT_QUERIES: Mapping[str, str] = {
    "tdp43_sepsis": "serum TDP-43 sepsis-associated encephalopathy",
    "tdp43_general": "serum TDP-43 brain injury biomarker",
    "traditional_markers": "(NSE OR S100B OR GFAP) sepsis brain injury prognosis",
}
MAX_FILENAME_LENGTH = 120
FILENAME_SANITIZER = re.compile(r"[^\w\-. ]+")


class LiteratureCrawler:
    """Orchestrates crawling across multiple PubMed queries."""

    def __init__(
        self,
        *,
        output_dir: Path | str = "data",
        queries: Mapping[str, str] | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.queries = dict(queries or DEFAULT_QUERIES)

    def run(self) -> dict[str, list[Article]]:
        """Run the multi-stage crawling workflow."""

        results: dict[str, list[Article]] = {}
        for name, query in self.queries.items():
            LOGGER.info("Crawling PubMed for %s", query)
            articles = crawl_pubmed_articles(query, retmax=50)
            results[name] = articles
            self._write_results(name, articles)
            self._download_citations(name, articles)
        self._write_summary(results)
        return results

    def _write_results(self, name: str, articles: Iterable[Article]) -> None:
        payload = [asdict(article) for article in articles]
        output_path = self.output_dir / f"{name}.json"
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        LOGGER.info("Saved %d articles to %s", len(payload), output_path)

    def _write_summary(self, results: Mapping[str, Sequence[Article]]) -> None:
        summary_path = self.output_dir / "summary.md"
        summary_lines = ["# Serum TDP-43 and Sepsis Literature Summary", ""]

        def summarize_articles(label: str, articles: Sequence[Article]) -> None:
            summary_lines.append(f"## {label}")
            if not articles:
                summary_lines.append("No articles retrieved.\n")
                return
            for article in articles:
                authors = "; ".join(article.authors[:5])
                if len(article.authors) > 5:
                    authors += " et al."
                summary_lines.append(
                    f"- **{article.title}** ({article.publication_date}) - {authors}. "
                    f"[{article.journal}]({article.url})"
                )
            summary_lines.append("")

        summarize_articles("Serum TDP-43 in Sepsis", results.get("tdp43_sepsis", []))
        summarize_articles("Serum TDP-43 in Brain Injury", results.get("tdp43_general", []))
        summarize_articles(
            "Traditional Brain Injury Biomarkers",
            results.get("traditional_markers", []),
        )

        summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
        LOGGER.info("Saved summary to %s", summary_path)

    def _download_citations(self, name: str, articles: Iterable[Article]) -> None:
        citation_dir = self.output_dir / "citations" / name
        citation_dir.mkdir(parents=True, exist_ok=True)

        for article in articles:
            if not article.pmid:
                LOGGER.debug(
                    "Skipping citation download for article without PMID: %s",
                    article.title,
                )
                continue
            try:
                citation_bytes = fetch_endnote_citation(article.pmid)
            except Exception as exc:  # pragma: no cover - network errors hard to reproduce
                LOGGER.warning(
                    "Failed to download EndNote citation for PMID %s (%s): %s",
                    article.pmid,
                    article.title,
                    exc,
                )
                continue

            filename = sanitize_title(article.title)
            citation_path = citation_dir / f"{filename or article.pmid}.nbib"

            # Avoid overwriting citations when titles collide by appending the PMID.
            if citation_path.exists():
                citation_path = citation_dir / f"{filename or article.pmid}-{article.pmid}.nbib"

            citation_path.write_bytes(citation_bytes)
            LOGGER.info("Saved EndNote citation for PMID %s to %s", article.pmid, citation_path)


def sanitize_title(title: str, *, max_length: int = MAX_FILENAME_LENGTH) -> str:
    """Generate a filesystem-friendly slug from an article title."""

    sanitized = FILENAME_SANITIZER.sub("", title).strip()
    sanitized = sanitized.replace(" ", "_")
    return sanitized[:max_length]


__all__ = ["Article", "LiteratureCrawler", "sanitize_title"]
