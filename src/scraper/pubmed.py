"""Utilities for crawling PubMed articles related to serum TDP-43 and sepsis."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Iterable, List, Mapping
from urllib import error, parse, request
from xml.etree import ElementTree as ET


LOGGER = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "TDP43-Sepsis-Project/1.0"
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 0.5
DEFAULT_TIMEOUT = 20


@dataclass(slots=True)
class Article:
    """Structured representation of a PubMed article."""

    pmid: str
    title: str
    authors: List[str]
    journal: str
    publication_date: str
    abstract: str
    url: str


class HttpResponse:
    """Minimal HTTP response wrapper mimicking the subset of ``requests.Response`` used."""

    def __init__(self, *, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content
        self.text = content.decode("utf-8", errors="ignore")

    def json(self) -> dict:
        return json.loads(self.text or "{}")


def _request_with_backoff(
    url: str,
    params: Mapping[str, str],
    *,
    retries: int = DEFAULT_RETRIES,
    delay: float = DEFAULT_BACKOFF,
    timeout: int = DEFAULT_TIMEOUT,
) -> HttpResponse:
    """Send a GET request with exponential backoff on transient failures."""

    headers = {"User-Agent": USER_AGENT}
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            query = parse.urlencode(params)
            req = request.Request(f"{url}?{query}", headers=headers)
            with request.urlopen(req, timeout=timeout) as resp:
                content = resp.read()
                return HttpResponse(status_code=resp.status, content=content)
        except error.HTTPError as exc:  # pragma: no cover - network failures are rare in tests
            last_error = exc
            LOGGER.warning("Request failed (%s): %s", exc.code, exc.reason)
            response = HttpResponse(status_code=exc.code, content=exc.read())
        except error.URLError as exc:  # pragma: no cover
            last_error = exc
            LOGGER.warning("Network error: %s", exc.reason)
            response = HttpResponse(status_code=0, content=b"")
        except Exception as exc:  # pragma: no cover - unexpected runtime errors
            last_error = exc
            LOGGER.warning("Unexpected error: %s", exc)
            response = HttpResponse(status_code=0, content=b"")

        LOGGER.warning("Request failed (%s): %s", response.status_code, response.text)
        if attempt < retries:
            time.sleep(delay * (2 ** (attempt - 1)))

    raise RuntimeError(f"Failed to fetch data from {url} after {retries} attempts") from last_error


def search_pubmed(query: str, *, retmax: int = 25) -> List[str]:
    """Search PubMed for a query and return a list of PMIDs."""

    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": str(retmax),
    }
    url = f"{EUTILS_BASE}/esearch.fcgi"
    response = _request_with_backoff(url, params)
    data = response.json()
    return data.get("esearchresult", {}).get("idlist", [])


def fetch_pubmed_details(pmids: Iterable[str]) -> List[Article]:
    """Fetch detailed information for a set of PMIDs."""

    ids = [pmid for pmid in pmids if pmid]
    if not ids:
        return []

    params = {
        "db": "pubmed",
        "retmode": "xml",
        "id": ",".join(ids),
    }
    url = f"{EUTILS_BASE}/efetch.fcgi"
    response = _request_with_backoff(url, params)

    root = ET.fromstring(response.content)
    articles: List[Article] = []

    for article in root.findall(".//PubmedArticle"):
        article_data = article.find("MedlineCitation/Article")
        if article_data is None:
            continue

        pmid = article.findtext("MedlineCitation/PMID") or ""
        title = article_data.findtext("ArticleTitle") or ""
        abstract_texts = [
            elem.text.strip() if elem.text else ""
            for elem in article_data.findall("Abstract/AbstractText")
        ]
        abstract = "\n".join(text for text in abstract_texts if text)
        journal = article_data.findtext("Journal/Title") or ""
        pub_date_node = article_data.find("Journal/JournalIssue/PubDate")
        if pub_date_node is not None:
            year = pub_date_node.findtext("Year") or ""
            month = pub_date_node.findtext("Month") or ""
            day = pub_date_node.findtext("Day") or ""
            pub_date = "-".join(part for part in [year, month, day] if part)
        else:
            pub_date = ""

        authors = []
        for author in article_data.findall("AuthorList/Author"):
            last_name = author.findtext("LastName") or ""
            fore_name = author.findtext("ForeName") or author.findtext("Initials") or ""
            if last_name or fore_name:
                full_name = ", ".join(filter(None, [last_name, fore_name]))
                authors.append(full_name)

        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
        articles.append(
            Article(
                pmid=pmid,
                title=title,
                authors=authors,
                journal=journal,
                publication_date=pub_date,
                abstract=abstract,
                url=url,
            )
        )

    return articles


def crawl_pubmed_articles(query: str, *, retmax: int = 25) -> List[Article]:
    """Convenience helper that performs a search followed by fetching article details."""

    pmids = search_pubmed(query, retmax=retmax)
    LOGGER.info("Found %d PMIDs for query '%s'", len(pmids), query)
    return fetch_pubmed_details(pmids)


def fetch_endnote_citation(pmid: str) -> bytes:
    """Download a PubMed citation in EndNote (NBIB) format for the given PMID."""

    if not pmid:
        raise ValueError("PMID is required to download citation data")

    params = {
        "db": "pubmed",
        "id": pmid,
        "retmode": "text",
        "rettype": "nbib",
    }
    url = f"{EUTILS_BASE}/efetch.fcgi"
    response = _request_with_backoff(url, params)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to download citation for PMID {pmid}")
    return response.content
