from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

import requests

from dart_digest.models import Disclosure


def fetch_today_rss(rss_url: str, timeout_seconds: int = 20) -> str:
    response = requests.get(rss_url, timeout=timeout_seconds)
    response.raise_for_status()
    return response.text


def parse_disclosures(rss_xml: str) -> list[Disclosure]:
    root = ET.fromstring(rss_xml)
    items = root.findall("./channel/item")
    disclosures: list[Disclosure] = []

    for item in items:
        title = _safe_text(item.find("title"))
        link = _safe_text(item.find("link"))
        description = _safe_text(item.find("description"))
        pub_date_raw = _safe_text(item.find("pubDate"))
        receipt_no = _extract_receipt_no(link)

        if not title or not link or not receipt_no:
            continue

        disclosures.append(
            Disclosure(
                company_name=extract_company_name(title),
                title=title,
                link=link,
                receipt_no=receipt_no,
                published_at=_parse_pub_date(pub_date_raw),
                description=description,
                raw={
                    "pub_date_raw": pub_date_raw,
                },
            )
        )

    return disclosures


def extract_company_name(title: str) -> str:
    title = title.strip()
    if not title:
        return ""

    # Typical format: "회사명 (공시제목)"
    company = title.split("(", maxsplit=1)[0].strip()
    if company:
        return company

    # Fallback for edge cases where title begins with brackets.
    cleaned = re.sub(r"^\[[^\]]+\]\s*", "", title)
    return cleaned.split(" ", maxsplit=1)[0].strip()


def _extract_receipt_no(link: str) -> str:
    parsed = urlparse(link)
    q = parse_qs(parsed.query)
    for key in ("rcpNo", "rcpno"):
        values = q.get(key)
        if values and values[0]:
            return values[0]

    # Some feeds embed receipt number in path text.
    match = re.search(r"(\d{14})", link)
    return match.group(1) if match else ""


def _parse_pub_date(pub_date_raw: str) -> datetime:
    if not pub_date_raw:
        return datetime.utcnow()

    try:
        dt = parsedate_to_datetime(pub_date_raw)
        if dt.tzinfo is None:
            return dt
        return dt.astimezone().replace(tzinfo=None)
    except (TypeError, ValueError):
        return datetime.utcnow()


def _safe_text(element: ET.Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""
