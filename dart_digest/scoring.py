from __future__ import annotations

import math
import re
from dataclasses import dataclass

from dart_digest.models import Disclosure, ScoredDisclosure


@dataclass(frozen=True)
class EventRule:
    event_type: str
    keywords: tuple[str, ...]
    event_score: float
    persistence_score: float
    reason: str


EVENT_RULES: tuple[EventRule, ...] = (
    EventRule(
        event_type="지배구조/자본변동",
        keywords=("유상증자", "무상증자", "감자", "전환사채", "신주인수권부사채"),
        event_score=95.0,
        persistence_score=88.0,
        reason="자본구조 변화는 희석/레버리지/주주가치에 중장기 영향을 줄 가능성이 큼",
    ),
    EventRule(
        event_type="M&A/사업재편",
        keywords=("합병", "분할", "영업양수", "영업양도", "주식양수도", "인수"),
        event_score=92.0,
        persistence_score=90.0,
        reason="사업 포트폴리오 재편은 이익체력과 밸류에이션 체계를 바꿀 수 있음",
    ),
    EventRule(
        event_type="감사/리스크",
        keywords=("감사의견", "의견거절", "한정", "부적정", "회생", "상장폐지", "영업정지"),
        event_score=96.0,
        persistence_score=84.0,
        reason="감사/규제 이벤트는 자금조달과 시장 신뢰도에 구조적 영향을 미칠 수 있음",
    ),
    EventRule(
        event_type="수주/계약",
        keywords=("단일판매", "공급계약", "장기공급", "수주"),
        event_score=85.0,
        persistence_score=82.0,
        reason="대형 계약은 중기 매출 가시성과 실적 추정치를 바꿀 수 있음",
    ),
    EventRule(
        event_type="실적/전망",
        keywords=("잠정실적", "영업실적", "실적", "매출액", "영업이익", "당기순이익", "전망"),
        event_score=80.0,
        persistence_score=75.0,
        reason="실적 체력 변화는 이익 추정과 멀티플 재평가로 이어질 수 있음",
    ),
    EventRule(
        event_type="지배주주/특수관계",
        keywords=("최대주주", "특수관계인", "임원", "자사주", "자기주식"),
        event_score=77.0,
        persistence_score=78.0,
        reason="지배주주 관련 이벤트는 거버넌스 프리미엄/디스카운트 요인",
    ),
    EventRule(
        event_type="주주환원",
        keywords=("배당", "자기주식취득", "소각", "주주환원"),
        event_score=72.0,
        persistence_score=70.0,
        reason="주주환원 정책은 장기 자본배분 기대를 바꿀 수 있음",
    ),
)


def score_disclosures(disclosures: list[Disclosure]) -> list[ScoredDisclosure]:
    return [score_disclosure(item) for item in disclosures]


def score_disclosure(disclosure: Disclosure) -> ScoredDisclosure:
    title = disclosure.title
    body = f"{disclosure.title}\n{disclosure.description}"

    event_type, event_score, persistence_score, reasons = _score_event(title)
    financial_score, financial_reason = _score_financial_impact(body)
    confidence_score, confidence_reason = _score_confidence(title, body)

    reasons.extend([financial_reason, confidence_reason])

    total = (
        event_score * 0.45
        + financial_score * 0.30
        + persistence_score * 0.15
        + confidence_score * 0.10
    )

    return ScoredDisclosure(
        disclosure=disclosure,
        event_type=event_type,
        event_score=event_score,
        financial_score=financial_score,
        persistence_score=persistence_score,
        confidence_score=confidence_score,
        total_score=round(total, 2),
        reasons=[reason for reason in reasons if reason],
    )


def _score_event(title: str) -> tuple[str, float, float, list[str]]:
    lowered = title.replace(" ", "")
    for rule in EVENT_RULES:
        if any(keyword in lowered for keyword in rule.keywords):
            return (
                rule.event_type,
                rule.event_score,
                rule.persistence_score,
                [rule.reason],
            )

    return (
        "기타",
        55.0,
        50.0,
        ["핵심 이벤트 분류에 직접 매칭되지 않아 보수적으로 평가"],
    )


def _score_financial_impact(text: str) -> tuple[float, str]:
    amount_score = _amount_based_score(text)
    pct_score = _percent_based_score(text)

    score = min(100.0, max(amount_score, pct_score))
    if score <= 40.0:
        return 40.0, "재무 임팩트를 뒷받침하는 수치 정보가 제한적"

    if amount_score >= pct_score:
        return score, "공시 내 금액 단서가 커 재무 영향 가능성을 높게 반영"
    return score, "공시 내 비율 변화 단서가 커 이익 변동성을 높게 반영"


def _amount_based_score(text: str) -> float:
    # Supports patterns like 1.2조, 3500억, 40000백만
    pattern = re.compile(r"(\d+(?:[.,]\d+)?)\s*(조|억|백만|천만|만원|원)")
    values: list[float] = []
    for number, unit in pattern.findall(text):
        num = float(number.replace(",", ""))
        multiplier = {
            "조": 1_0000_0000_0000,
            "억": 1_0000_0000,
            "백만": 1_000_000,
            "천만": 10_000_000,
            "만원": 10_000,
            "원": 1,
        }[unit]
        values.append(num * multiplier)

    if not values:
        return 35.0

    max_value = max(values)
    # 1e8 KRW = 50, 1e10 KRW ~= 70, 1e12 KRW ~= 90
    log_scale = math.log10(max(max_value, 1))
    return min(100.0, max(50.0, 20.0 + log_scale * 6.0))


def _percent_based_score(text: str) -> float:
    matches = [float(v) for v in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)]
    if not matches:
        return 30.0

    high = max(matches)
    if high >= 100:
        return 85.0
    if high >= 50:
        return 78.0
    if high >= 20:
        return 70.0
    if high >= 10:
        return 60.0
    return 50.0


def _score_confidence(title: str, text: str) -> tuple[float, str]:
    score = 55.0
    reason_parts: list[str] = []

    if re.search(r"\d", text):
        score += 15.0
        reason_parts.append("숫자 단서 포함")

    if "정정" in title:
        score -= 12.0
        reason_parts.append("정정공시로 불확실성 가중")

    if len(title) >= 12:
        score += 8.0
        reason_parts.append("제목 정보량 충분")

    if any(x in title for x in ["결정", "체결", "확정", "승인"]):
        score += 10.0
        reason_parts.append("행위의 확정성 단어 포함")

    score = max(30.0, min(95.0, score))
    if not reason_parts:
        return score, "신뢰도를 높이는 구조적 단서가 제한적"
    return score, "신뢰도 판단: " + ", ".join(reason_parts)
