from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Disclosure:
    company_name: str
    title: str
    link: str
    receipt_no: str
    published_at: datetime
    description: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoredDisclosure:
    disclosure: Disclosure
    market: str
    event_type: str
    event_score: float
    financial_score: float
    persistence_score: float
    confidence_score: float
    market_bonus: float
    total_score: float
    reasons: list[str]


@dataclass
class DailySelection:
    run_date: datetime
    selected: list[ScoredDisclosure]
    generated_article: str
