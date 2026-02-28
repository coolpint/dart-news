from __future__ import annotations

import argparse
import sys

from dart_digest.config import Settings
from dart_digest.pipeline import DigestPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dart-digest",
        description="Generate and publish a daily deep-dive report from DART disclosures.",
    )
    parser.add_argument("run", nargs="?", default="run", help="Run pipeline once")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Include previously processed disclosures (skip dedup filter).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate report without publishing to Slack.",
    )
    parser.add_argument(
        "--print-article",
        action="store_true",
        help="Print generated article to stdout.",
    )
    parser.add_argument(
        "--date",
        help="Historical date for backtest in YYYYMMDD (uses OpenDART list API).",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    settings = Settings.from_env()
    if args.dry_run:
        settings.dry_run = True

    pipeline = DigestPipeline(settings)

    try:
        result = pipeline.run(force=args.force, test_date=args.date)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print(f"[{result.status}] {result.message}")

    if args.print_article and result.selection:
        print("\n" + result.selection.generated_article)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
