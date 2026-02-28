from __future__ import annotations

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
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
    published_ts: float


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
    ranked = _rank_news(filtered, company_name, disclosure_title, event_type)
    return ranked[:max_items]


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
                published_ts=_parse_pub_ts(pub_date),
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


def _rank_news(
    items: Iterable[NewsItem],
    company_name: str,
    disclosure_title: str,
    event_type: str,
) -> list[NewsItem]:
    now_ts = datetime.now(timezone.utc).timestamp()
    company = company_name.replace(" ", "")
    issue_keywords = _build_issue_keywords(disclosure_title, event_type)

    scored: list[tuple[float, NewsItem]] = []
    for item in items:
        title_compact = item.title.replace(" ", "")
        score = 0.0

        if company and company in title_compact:
            score += 5.0

        for kw in issue_keywords:
            if kw and kw in title_compact:
                score += 2.0

        if any(k in title_compact for k in ["적자전환", "흑자전환", "영업손실", "당기순손실"]):
            score += 2.5

        if item.published_ts > 0:
            age_days = (now_ts - item.published_ts) / 86400.0
            if age_days > 365:
                continue
            if age_days <= 30:
                score += 3.0
            elif age_days <= 90:
                score += 2.0
            elif age_days <= 180:
                score += 1.0

        scored.append((score, item))

    scored.sort(key=lambda x: (x[0], x[1].published_ts), reverse=True)
    return [item for _, item in scored]


def _build_issue_keywords(disclosure_title: str, event_type: str) -> list[str]:
    compact = disclosure_title.replace(" ", "")
    keywords: list[str] = []
    for kw in ["적자전환", "흑자전환", "영업손실", "당기순손실", "유상증자", "감사의견", "수주", "공급계약"]:
        if kw in compact:
            keywords.append(kw)

    event_defaults = {
        "지배구조/자본변동": ["유상증자", "전환사채", "희석"],
        "M&A/사업재편": ["합병", "인수", "분할"],
        "감사/리스크": ["감사의견", "의견거절", "리스크"],
        "수주/계약": ["수주", "공급계약"],
        "실적/전망": ["실적", "영업이익", "적자전환", "흑자전환"],
        "지배주주/특수관계": ["최대주주", "지배구조"],
        "주주환원": ["배당", "자사주"],
    }
    keywords.extend(event_defaults.get(event_type, []))

    # Deduplicate while preserving order.
    return list(dict.fromkeys(keywords))


def _format_pub_date(raw: str) -> str:
    if not raw:
        return ""

    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return raw


def _parse_pub_ts(raw: str) -> float:
    if not raw:
        return 0.0

    try:
        dt = parsedate_to_datetime(raw)
        return dt.timestamp()
    except (TypeError, ValueError):
        return 0.0


def _safe_text(element: ET.Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""
