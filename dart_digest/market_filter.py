from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from dart_digest.models import Disclosure


@dataclass
class CompanyInfo:
    company_name: str
    ticker: str
    market: str


class CompanyUniverse:
    def __init__(self, items: dict[str, CompanyInfo]) -> None:
        self.items = items

    @classmethod
    def from_csv(cls, csv_path: Path) -> "CompanyUniverse":
        if not csv_path.exists():
            raise FileNotFoundError(f"Company map not found: {csv_path}")

        items: dict[str, CompanyInfo] = {}
        with csv_path.open("r", encoding="utf-8") as fp:
            reader = csv.DictReader(fp)
            required = {"company_name", "ticker", "market"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError(
                    "company map CSV must contain columns: company_name,ticker,market"
                )

            for row in reader:
                company_name = (row.get("company_name") or "").strip()
                ticker = (row.get("ticker") or "").strip()
                market = (row.get("market") or "").strip().upper()

                if not company_name or not market:
                    continue

                key = normalize_name(company_name)
                items[key] = CompanyInfo(
                    company_name=company_name,
                    ticker=ticker,
                    market=market,
                )

        return cls(items)

    def get_company(self, name: str) -> CompanyInfo | None:
        key = normalize_name(name)
        if key in self.items:
            return self.items[key]

        # Relaxed match fallback for parenthesized suffixes.
        relaxed = re.sub(r"\([^\)]*\)", "", key)
        return self.items.get(relaxed)


class KospiFilter:
    def __init__(self, universe: CompanyUniverse) -> None:
        self.universe = universe

    def filter(self, disclosures: list[Disclosure]) -> list[Disclosure]:
        filtered: list[Disclosure] = []
        for item in disclosures:
            company = self.universe.get_company(item.company_name)
            if company and company.market == "KOSPI":
                filtered.append(item)
        return filtered


def normalize_name(name: str) -> str:
    s = name.strip().upper()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[\.·ㆍ,'\"]", "", s)
    return s
