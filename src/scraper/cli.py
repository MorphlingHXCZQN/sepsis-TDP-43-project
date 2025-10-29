"""Command line interface for running the literature crawling workflow."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .sepsis_project import LiteratureCrawler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crawl PubMed for serum TDP-43 and sepsis brain injury literature."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="Directory where JSON and summary outputs will be stored.",
    )
    parser.add_argument(
        "--queries",
        type=Path,
        help="Optional path to a JSON file mapping query names to search terms.",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=50,
        help="Maximum number of PubMed articles to fetch per query.",
    )
    parser.add_argument(
        "--skip-citations",
        action="store_true",
        help="Disable downloading EndNote citation files (useful for dry runs).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (e.g. INFO, DEBUG).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s: %(message)s")

    if args.queries:
        try:
            queries_data = json.loads(args.queries.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
            raise SystemExit(f"Failed to parse queries file {args.queries}: {exc}") from exc
        if not isinstance(queries_data, dict):  # pragma: no cover - defensive branch
            raise SystemExit("Queries file must contain a JSON object mapping names to terms")
        queries = {str(key): str(value) for key, value in queries_data.items()}
    else:
        queries = None

    crawler = LiteratureCrawler(
        output_dir=args.output_dir,
        queries=queries,
        max_articles=args.max_articles,
        skip_citations=args.skip_citations,
    )
    crawler.run()


if __name__ == "__main__":
    main()
