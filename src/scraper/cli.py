"""Command line interface for running the literature crawling workflow."""
from __future__ import annotations

import argparse
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
        "--log-level",
        default="INFO",
        help="Logging level (e.g. INFO, DEBUG).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level.upper())
    crawler = LiteratureCrawler(output_dir=args.output_dir)
    crawler.run()


if __name__ == "__main__":
    main()
