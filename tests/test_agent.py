from __future__ import annotations

from pathlib import Path

from scraper.agent import AgentConfig, CrawlerAgent


class CitationFailingCrawler:
    def __init__(self, *, skip_citations: bool, **_: object) -> None:
        self.skip_citations = skip_citations
        self.report = {"query": {"articles_retrieved": 1, "citations_saved": 0, "missing_pmids": 0}}

    def run(self) -> dict[str, list[str]]:
        if not self.skip_citations:
            raise RuntimeError("Failed to download citation for PMID 123")
        return {"query": ["article"]}


class FetchFailCrawler:
    def __init__(self, *, max_articles: int, **_: object) -> None:
        self.max_articles = max_articles
        self.report = {"query": {"articles_retrieved": 0, "citations_saved": 0, "missing_pmids": 0}}

    def run(self) -> dict[str, list[str]]:
        if self.max_articles > 20:
            raise RuntimeError("Failed to fetch data from server")
        return {"query": []}


class MissingPmidsCrawler:
    def __init__(self, *, skip_citations: bool, **_: object) -> None:
        self.report = {"query": {"articles_retrieved": 1, "citations_saved": 0, "missing_pmids": 1}}

    def run(self) -> dict[str, list[str]]:
        return {"query": ["article"]}


def test_agent_enables_skip_citations(tmp_path: Path) -> None:
    config = AgentConfig(output_dir=tmp_path, queries={"query": "term"}, max_articles=40, skip_citations=False)
    agent = CrawlerAgent(config=config, max_attempts=2, crawler_factory=CitationFailingCrawler)

    result = agent.run()

    assert result.success is True
    assert result.attempts == 2
    assert agent.config.skip_citations is True
    assert result.errors[0].fix_applied == "Enabled skip_citations after citation failure"


def test_agent_reduces_max_articles(tmp_path: Path) -> None:
    config = AgentConfig(output_dir=tmp_path, queries={"query": "term"}, max_articles=40)
    agent = CrawlerAgent(config=config, max_attempts=3, crawler_factory=FetchFailCrawler)

    result = agent.run()

    assert result.success is True
    assert result.attempts == 2
    assert agent.config.max_articles == 20
    assert any("returned no articles" in note for note in result.notes)


def test_agent_notes_missing_pmids(tmp_path: Path) -> None:
    config = AgentConfig(output_dir=tmp_path, queries={"query": "term"}, max_articles=10)
    agent = CrawlerAgent(config=config, crawler_factory=MissingPmidsCrawler)

    result = agent.run()

    assert result.success is True
    assert any("without PMIDs" in note for note in result.notes)
    assert any("saved no citations" in note for note in result.notes)
