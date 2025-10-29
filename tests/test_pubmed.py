from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from scraper import pubmed
from scraper.sepsis_project import LiteratureCrawler, sanitize_title


class DummyResponse:
    def __init__(self, *, json_data=None, content: bytes = b"", status_code: int = 200):
        self._json_data = json_data
        self.content = content
        self.status_code = status_code
        self.text = content.decode("utf-8", errors="ignore")

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON data provided")
        return self._json_data


@pytest.fixture
def sample_article_xml() -> bytes:
    return b"""
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>12345</PMID>
          <Article>
            <ArticleTitle>Serum TDP-43 levels in sepsis</ArticleTitle>
            <Abstract>
              <AbstractText>Background details.</AbstractText>
            </Abstract>
            <Journal>
              <JournalIssue>
                <PubDate>
                  <Year>2023</Year>
                  <Month>05</Month>
                  <Day>12</Day>
                </PubDate>
              </JournalIssue>
              <Title>Critical Care Medicine</Title>
            </Journal>
            <AuthorList>
              <Author>
                <LastName>Smith</LastName>
                <ForeName>Alice</ForeName>
              </Author>
              <Author>
                <LastName>Jones</LastName>
                <Initials>BC</Initials>
              </Author>
            </AuthorList>
          </Article>
        </MedlineCitation>
      </PubmedArticle>
    </PubmedArticleSet>
    """.strip()


def test_search_pubmed(monkeypatch):
    response = DummyResponse(json_data={"esearchresult": {"idlist": ["1", "2"]}})

    def fake_request(url, params, **_):
        return response

    monkeypatch.setattr(pubmed, "_request_with_backoff", fake_request)

    ids = pubmed.search_pubmed("test query", retmax=5)

    assert ids == ["1", "2"]


def test_fetch_pubmed_details(monkeypatch, sample_article_xml):
    response = DummyResponse(content=sample_article_xml)
    monkeypatch.setattr(pubmed, "_request_with_backoff", Mock(return_value=response))

    articles = pubmed.fetch_pubmed_details(["12345"])

    assert len(articles) == 1
    article = articles[0]
    assert article.pmid == "12345"
    assert article.title == "Serum TDP-43 levels in sepsis"
    assert "Smith" in article.authors[0]
    assert article.journal == "Critical Care Medicine"
    assert article.publication_date == "2023-05-12"
    assert article.abstract.startswith("Background")
    assert article.url.endswith("12345/")


def test_fetch_endnote_citation(monkeypatch):
    response = DummyResponse(content=b"NBIB", status_code=200)

    def fake_request(url, params, **_):
        assert params["rettype"] == "nbib"
        assert params["id"] == "123"
        return response

    monkeypatch.setattr(pubmed, "_request_with_backoff", fake_request)

    citation = pubmed.fetch_endnote_citation("123")
    assert citation == b"NBIB"

    with pytest.raises(ValueError):
        pubmed.fetch_endnote_citation("")


def test_crawler_writes_outputs(tmp_path: Path, monkeypatch, sample_article_xml):
    response_search = DummyResponse(json_data={"esearchresult": {"idlist": ["12345"]}})
    response_fetch = DummyResponse(content=sample_article_xml)

    def fake_request(url, params, **_):
        if params.get("retmode") == "json":
            return response_search
        return response_fetch

    monkeypatch.setattr(pubmed, "_request_with_backoff", fake_request)
    monkeypatch.setattr("scraper.sepsis_project.fetch_endnote_citation", Mock(return_value=b"NBIB"))

    crawler = LiteratureCrawler(output_dir=tmp_path, max_articles=40)
    results = crawler.run()

    assert all(results[key] for key in ["tdp43_sepsis", "tdp43_general", "traditional_markers"])
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "Serum TDP-43" in summary
    for key in ["tdp43_sepsis", "tdp43_general", "traditional_markers"]:
        data = json.loads((tmp_path / f"{key}.json").read_text(encoding="utf-8"))
        assert data[0]["pmid"] == "12345"
        citation_files = list((tmp_path / "citations" / key).glob("*.nbib"))
        assert citation_files, "Expected citation file to be written"
        assert citation_files[0].read_bytes() == b"NBIB"

    report = crawler.report
    assert set(report) == {"tdp43_sepsis", "tdp43_general", "traditional_markers"}
    for metrics in report.values():
        assert metrics["articles_retrieved"] == 1
        assert metrics["citations_saved"] == 1
        assert metrics["missing_pmids"] == 0


def test_crawler_respects_max_articles(tmp_path: Path, monkeypatch):
    calls: list[int] = []

    def fake_crawl(query: str, *, retmax: int) -> list[pubmed.Article]:
        calls.append(retmax)
        return []

    monkeypatch.setattr("scraper.sepsis_project.crawl_pubmed_articles", fake_crawl)

    crawler = LiteratureCrawler(output_dir=tmp_path, max_articles=5, skip_citations=True)
    crawler.run()

    assert calls == [5, 5, 5]


def test_crawler_skip_citations(tmp_path: Path, monkeypatch):
    article = pubmed.Article(
        pmid="123",
        title="Test",
        authors=["Smith"],
        journal="Journal",
        publication_date="2024",
        abstract="",
        url="https://example.com",
    )

    monkeypatch.setattr(
        "scraper.sepsis_project.crawl_pubmed_articles",
        Mock(return_value=[article]),
    )
    crawler = LiteratureCrawler(output_dir=tmp_path, max_articles=2, skip_citations=True)
    crawler.run()

    assert not list((tmp_path / "citations").rglob("*.nbib"))
    metrics = crawler.report["tdp43_sepsis"]
    assert metrics["citations_saved"] == 0
    assert metrics["missing_pmids"] == 0


def test_crawler_reports_missing_pmids(tmp_path: Path, monkeypatch):
    article_missing = pubmed.Article(
        pmid="",
        title="Missing PMID",
        authors=["Lee"],
        journal="Journal",
        publication_date="2024",
        abstract="",
        url="https://example.com",
    )

    monkeypatch.setattr(
        "scraper.sepsis_project.crawl_pubmed_articles",
        Mock(return_value=[article_missing]),
    )
    monkeypatch.setattr("scraper.sepsis_project.fetch_endnote_citation", Mock())

    crawler = LiteratureCrawler(output_dir=tmp_path, skip_citations=False)
    crawler.run()

    metrics = crawler.report["tdp43_sepsis"]
    assert metrics["citations_saved"] == 0
    assert metrics["missing_pmids"] == 1


def test_sanitize_title_handles_problematic_characters():
    title = "A complex: title/with?characters*"
    sanitized = sanitize_title(title)
    assert sanitized.startswith("A_complex_title")
    assert "?" not in sanitized
