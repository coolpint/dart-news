#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests


KRX_URLS = {
    "KOSPI": "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType=stockMkt",
    "KOSDAQ": "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType=kosdaqMkt",
}


@dataclass
class CompanyRow:
    company_name: str
    ticker: str
    market: str


def fetch_market_rows(market: str, timeout: int = 30) -> list[CompanyRow]:
    url = KRX_URLS[market]
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    text = response.content.decode("euc-kr", errors="replace")
    rows: list[CompanyRow] = []

    for raw_row in _extract_rows(text):
        cells = _extract_cells(raw_row)
        if len(cells) < 3:
            continue

        if cells[0] == "회사명":
            continue

        company_name = _normalize_text(cells[0])
        market_cell = _normalize_text(cells[1])
        ticker = _normalize_text(cells[2]).upper()

        if not company_name or not ticker:
            continue

        resolved_market = market
        if "코스닥" in market_cell:
            resolved_market = "KOSDAQ"
        elif "유가" in market_cell:
            resolved_market = "KOSPI"

        rows.append(
            CompanyRow(
                company_name=company_name,
                ticker=ticker,
                market=resolved_market,
            )
        )

    return rows


def write_company_map(rows: Iterable[CompanyRow], out_path: Path) -> int:
    unique: dict[tuple[str, str], CompanyRow] = {}
    for row in rows:
        key = (row.company_name, row.ticker)
        unique[key] = row

    ordered = sorted(unique.values(), key=lambda x: (x.market, x.company_name, x.ticker))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["company_name", "ticker", "market"])
        for row in ordered:
            writer.writerow([row.company_name, row.ticker, row.market])

    return len(ordered)


def _extract_rows(html_text: str) -> list[str]:
    return re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, flags=re.IGNORECASE | re.DOTALL)


def _extract_cells(row_html: str) -> list[str]:
    return re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.IGNORECASE | re.DOTALL)


def _normalize_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    decoded = html.unescape(without_tags)
    collapsed = re.sub(r"\s+", " ", decoded)
    return collapsed.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Update KOSPI/KOSDAQ company map from KRX")
    parser.add_argument(
        "--output",
        default="data/company_map.csv",
        help="Output CSV path (default: data/company_map.csv)",
    )
    args = parser.parse_args()

    output_path = Path(args.output)

    rows: list[CompanyRow] = []
    for market in ("KOSPI", "KOSDAQ"):
        market_rows = fetch_market_rows(market)
        rows.extend(market_rows)

    count = write_company_map(rows, output_path)
    print(f"wrote {count} companies to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
