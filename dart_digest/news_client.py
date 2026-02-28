from __future__ import annotations

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import requests


GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published_at: str


def search_related_news(
    company_name: str,
    disclosure_title: str,
    event_type: str,
    max_items: int = 2,
) -> list[NewsItem]:
    query = _build_query(company_name, disclosure_title, event_type)
    params = {
        "q": query,
        "hl": "ko",
        "gl": "KR",
        "ceid": "KR:ko",
    }
    url = f"{GOOGLE_NEWS_RSS}?{urlencode(params)}"

    try:
        response = requests.get(
            url,
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (compatible; dart-news-bot/1.0)"},
        )
        response.raise_for_status()
    except requests.RequestException:
        return []

    items = parse_google_news_rss(response.text)
    filtered = _filter_relevant_news(items, company_name)
    return filtered[:max_items]


def parse_google_news_rss(rss_xml: str) -> list[NewsItem]:
    try:
        root = ET.fromstring(rss_xml)
    except ET.ParseError:
        return []

    result: list[NewsItem] = []
    for item in root.findall("./channel/item"):
        title = _safe_text(item.find("title"))
        link = _safe_text(item.find("link"))
        source = _safe_text(item.find("source"))
        pub_date = _safe_text(item.find("pubDate"))
        if not title or not link:
            continue

        result.append(
            NewsItem(
                title=title,
                link=link,
                source=source,
                published_at=_format_pub_date(pub_date),
            )
        )

    return result


def _build_query(company_name: str, disclosure_title: str, event_type: str) -> str:
    compact = disclosure_title.replace(company_name, "").strip()
    compact = compact.replace("(", " ").replace(")", " ")
    compact = " ".join(compact.split())

    event_hint = {
        "지배구조/자본변동": "유상증자 감자 전환사채",
        "M&A/사업재편": "합병 인수 분할",
        "감사/리스크": "감사의견 리스크",
        "수주/계약": "공급계약 수주",
        "실적/전망": "실적 전망",
        "지배주주/특수관계": "최대주주 지배구조",
        "주주환원": "배당 자사주",
    }.get(event_type, "공시")

    return f"{company_name} {compact} {event_hint}".strip()


def _filter_relevant_news(items: Iterable[NewsItem], company_name: str) -> list[NewsItem]:
    dedup: dict[str, NewsItem] = {}
    company = company_name.replace(" ", "")

    for item in items:
        key = item.link.strip()
        if not key or key in dedup:
            continue

        title_compact = item.title.replace(" ", "")
        if company and company not in title_compact:
            # Keep limited fallback coverage even if exact match is missing.
            if len(dedup) >= 6:
                continue

        dedup[key] = item

    return list(dedup.values())


def _format_pub_date(raw: str) -> str:
    if not raw:
        return ""

    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return raw


def _safe_text(element: ET.Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""
