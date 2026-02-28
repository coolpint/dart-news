from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime

import requests

from dart_digest.config import Settings
from dart_digest.models import ScoredDisclosure
from dart_digest.news_client import NewsItem, search_related_news


@dataclass
class IssueContext:
    profitability_signal: str
    company_plan_signal: str
    core_business_headwind: str


class ArticleWriter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def write(self, selected: list[ScoredDisclosure], run_dt: datetime) -> str:
        if not selected:
            return "오늘은 분석 대상 공시가 없습니다."

        news_map = self._collect_related_news(selected)

        article = ""
        if self.settings.openai_api_key:
            article = self._write_with_openai(selected, run_dt, news_map)

        if not article:
            article = self._write_template(selected, run_dt, news_map)

        if not _passes_fact_gate(article, selected):
            return self._write_template(selected, run_dt, news_map)
        return article

    def _collect_related_news(
        self,
        selected: list[ScoredDisclosure],
    ) -> dict[str, list[NewsItem]]:
        news_map: dict[str, list[NewsItem]] = {}
        for item in selected:
            disclosure = item.disclosure
            news_map[disclosure.receipt_no] = search_related_news(
                company_name=disclosure.company_name,
                disclosure_title=disclosure.title,
                event_type=item.event_type,
                max_items=2,
            )
        return news_map

    def _write_with_openai(
        self,
        selected: list[ScoredDisclosure],
        run_dt: datetime,
        news_map: dict[str, list[NewsItem]],
    ) -> str:
        system_prompt = (
            "당신은 한국 증권업계 셀사이드 애널리스트 출신의 경제부 베테랑 기자다. "
            "DART 공시를 바탕으로 중장기 가치 영향 중심의 심층 기사만 작성한다. "
            "사실과 추론을 분리하고, 투자권유처럼 보이는 단정 표현을 피한다."
        )

        payload = {
            "model": self.settings.openai_model,
            "input": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": _build_user_prompt(selected, run_dt, news_map),
                },
            ],
            "temperature": 0.2,
        }

        try:
            response = requests.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=40,
            )
            response.raise_for_status()
        except requests.RequestException:
            return ""

        data = response.json()

        try:
            output = data.get("output", [])
            text_chunks: list[str] = []
            for item in output:
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        text_chunks.append(content.get("text", ""))
            return "\n".join([chunk.strip() for chunk in text_chunks if chunk.strip()]).strip()
        except (TypeError, AttributeError):
            return ""

    def _write_template(
        self,
        selected: list[ScoredDisclosure],
        run_dt: datetime,
        news_map: dict[str, list[NewsItem]],
    ) -> str:
        headline = _build_headline(selected)
        summary_lines = _build_summary(selected)

        body_blocks: list[str] = []
        for rank, item in enumerate(selected, start=1):
            disclosure = item.disclosure
            news_items = news_map.get(disclosure.receipt_no, [])
            issue_ctx = _build_issue_context(item, news_items)
            sentiment, sentiment_reason = _investor_impact(item, issue_ctx)

            body_blocks.append(
                "\n".join(
                    [
                        f"## {rank}. {disclosure.company_name} - {item.event_type}",
                        f"- 종합 중요도: {item.total_score:.1f} / 100"
                        + (
                            f" (시장가중치 +{item.market_bonus:.1f})"
                            if item.market_bonus > 0
                            else ""
                        ),
                        "",
                        "### 핵심 판단 근거 (상세)",
                        _detailed_rationale(item, issue_ctx),
                        "",
                        "### 투자자 관점 해석",
                        f"- 판단: **{sentiment}**",
                        f"- 해석: {sentiment_reason}",
                        "",
                        "### 전문가 시각에서 본 큰 의미",
                        _expert_insight(item, issue_ctx),
                        "",
                        "### 관련 뉴스 요약",
                        _related_news_summary(news_items, disclosure.company_name, issue_ctx),
                    ]
                )
            )

        disclaimer = (
            "\n\n---\n"
            "본 콘텐츠는 정보 제공 목적이며, 특정 종목의 매수·매도 추천이 아닙니다. "
            "투자 판단과 책임은 투자자 본인에게 있습니다."
        )

        return "\n\n".join(
            [
                f"# {headline}",
                f"작성시각: {run_dt.strftime('%Y-%m-%d %H:%M:%S')}",
                "\n".join(summary_lines),
                *body_blocks,
            ]
        ) + disclaimer


def _build_user_prompt(
    selected: list[ScoredDisclosure],
    run_dt: datetime,
    news_map: dict[str, list[NewsItem]],
) -> str:
    facts = []
    for idx, item in enumerate(selected, start=1):
        d = item.disclosure
        issue_ctx = _build_issue_context(item, news_map.get(d.receipt_no, []))
        sentiment, sentiment_reason = _investor_impact(item, issue_ctx)
        facts.append(
            {
                "rank": idx,
                "company": d.company_name,
                "title": d.title,
                "published_at": d.published_at.isoformat(timespec="seconds"),
                "event_type": item.event_type,
                "market": item.market,
                "market_bonus": item.market_bonus,
                "score": item.total_score,
                "reasons": item.reasons,
                "description": d.description,
                "issue_context": {
                    "profitability_signal": issue_ctx.profitability_signal,
                    "company_plan_signal": issue_ctx.company_plan_signal,
                    "core_business_headwind": issue_ctx.core_business_headwind,
                },
                "investor_view": {
                    "label": sentiment,
                    "reason": sentiment_reason,
                },
                "related_news": [
                    {
                        "title": n.title,
                        "source": n.source,
                        "published_at": n.published_at,
                        "link": n.link,
                    }
                    for n in news_map.get(d.receipt_no, [])
                ],
            }
        )

    return (
        f"기준시각: {run_dt.isoformat(timespec='seconds')}\n"
        "아래 공시 후보를 대상으로 심층 기사 작성:\n"
        f"```json\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n```\n"
        "요구사항:\n"
        "1) 제목 1개, 핵심요약 2줄, 본문(사실/해석 분리)을 포함\n"
        "2) 공시명/접수번호를 나열하지 말고, 왜 경영/가치에 중요한지 구체적으로 설명\n"
        "3) 적자전환/흑자전환 등 손익구조 변화가 있으면 반드시 명시하고 장기 영향 설명\n"
        "4) 회사가 제시한 향후 사업 계획과 현재 주력 사업의 어려움을 분리해 분석\n"
        "5) 투자자 관점에서 긍정/부정/중립 판단과 이유를 분명히 제시\n"
        "6) 회사의 중립적 문구 뒤에 숨은 회계/자본배분/리스크 의미를 전문가 시각으로 해석\n"
        "7) '관련 뉴스 요약' 섹션에서 제공된 링크만 사용해 최대 2개 기사 요약과 링크 제시\n"
        "8) 마지막에 투자권유 아님 면책 1문장\n"
    )


def _build_headline(selected: list[ScoredDisclosure]) -> str:
    first = selected[0]
    if len(selected) == 1:
        return f"{first.disclosure.company_name} 공시 심층: 장기 가치에 미치는 실질 영향"
    second = selected[1]
    return (
        f"오늘의 핵심 공시 2선: {first.disclosure.company_name}·"
        f"{second.disclosure.company_name}의 장기 가치 재평가 포인트"
    )


def _build_summary(selected: list[ScoredDisclosure]) -> list[str]:
    joined = ", ".join(
        [f"{item.disclosure.company_name}({item.event_type})" for item in selected]
    )
    avg_score = sum(item.total_score for item in selected) / max(len(selected), 1)

    return [
        "## 핵심 요약",
        f"- 오늘 핵심 이슈: {joined}",
        (
            "- 핵심 해석: 단기 변동성보다 자본구조·현금흐름·거버넌스 변화가 "
            f"중장기 가치(평균 중요도 {avg_score:.1f}점)에 미치는 영향을 중점 분석"
        ),
    ]


def _detailed_rationale(item: ScoredDisclosure, issue_ctx: IssueContext) -> str:
    disclosure = item.disclosure
    numbers = _extract_key_numbers(f"{disclosure.title} {disclosure.description}")
    num_text = ", ".join(numbers[:4]) if numbers else "핵심 숫자 단서 제한적"

    lines = [
        f"- 이벤트 분류 근거: {item.event_type} / {item.reasons[0] if item.reasons else '분류 근거 제한적'}",
        (
            "- 재무 영향 해석: 재무영향 점수 "
            f"{item.financial_score:.1f}, 지속성 점수 {item.persistence_score:.1f}, "
            f"신뢰도 점수 {item.confidence_score:.1f}"
        ),
        f"- 숫자 단서: {num_text}",
        f"- 손익 구조 변화: {issue_ctx.profitability_signal}",
        f"- 회사가 제시한 향후 계획: {issue_ctx.company_plan_signal}",
        f"- 현재 주력 사업의 어려움: {issue_ctx.core_business_headwind}",
        (
            "- 경영적 함의: 해당 공시는 일회성 뉴스보다 자본배분·수익성 구조·"
            "리스크 관리 체계를 바꿀 수 있는 성격인지가 핵심"
        ),
    ]
    return "\n".join(lines)


def _expert_insight(item: ScoredDisclosure, issue_ctx: IssueContext) -> str:
    title = item.disclosure.title
    text = f"{title} {item.disclosure.description}".replace(" ", "")

    if any(k in text for k in ["유상증자", "전환사채", "신주인수권부사채"]):
        return (
            "회계/자본시장 관점에서 핵심은 희석효과와 자금 사용처의 질이다. "
            "조달 자체보다 조달금이 ROIC를 높이는 투자로 연결되는지, 기존 주주가치 훼손을 상쇄할 만큼 "
            "현금흐름 개선이 가능한지가 장기 밸류에이션의 분기점이다."
        )

    if any(k in text for k in ["감사의견", "의견거절", "부적정", "한정"]):
        return (
            "핵심은 손익 숫자보다 신뢰성 프리미엄의 훼손 여부다. "
            "감사 이슈는 자금조달 비용과 거래상대방 신뢰에 연쇄적으로 영향을 주기 때문에, "
            "이후 해소 공시의 속도와 강도가 기업가치 회복 속도를 좌우한다."
        )

    if any(k in text for k in ["공급계약", "수주", "단일판매"]):
        return (
            "수주 공시는 매출 증가 자체보다 수익성의 질이 중요하다. "
            "계약 단가·원가 구조·납기 리스크를 감안했을 때 실제 영업현금흐름으로 이어지는지 확인해야 하며, "
            "백로그가 이익 가시성으로 전환되는 속도가 장기 주가의 핵심 변수다."
        )

    if any(k in text for k in ["합병", "분할", "인수", "영업양수", "영업양도"]):
        return (
            "사업재편 공시는 EPS 효과만 보면 왜곡될 수 있다. "
            "진짜 포인트는 사업 포트폴리오의 리스크/수익 구조가 개선되는지, "
            "그리고 통합 이후 고정비 효율화와 자본회전율 개선이 가능한지다."
        )

    if "적자전환" in issue_ctx.profitability_signal:
        return (
            "적자전환 국면에서 핵심은 '적자 자체'보다 적자의 원인과 회복 경로다. "
            "회사 측의 성장 스토리가 실제로 매출총이익률 반등·고정비 흡수 개선으로 이어지지 않으면 "
            "밸류에이션 디스카운트가 장기화될 가능성이 높다."
        )

    return (
        "전문가 관점의 핵심은 공시 문구의 수사보다 숫자와 실행 가능성이다. "
        "회사가 제시한 계획이 실제 분기 실적과 현금흐름으로 검증될 때만 장기 가치 재평가가 정당화된다."
    )


def _investor_impact(item: ScoredDisclosure, issue_ctx: IssueContext) -> tuple[str, str]:
    text = f"{item.disclosure.title} {item.disclosure.description}".replace(" ", "")

    negative = [
        "유상증자",
        "전환사채",
        "신주인수권부사채",
        "감사의견",
        "의견거절",
        "부적정",
        "한정",
        "상장폐지",
        "영업정지",
        "회생",
        "적자전환",
        "영업손실",
        "당기순손실",
    ]
    positive = [
        "무상증자",
        "배당",
        "자기주식취득",
        "소각",
        "공급계약",
        "수주",
        "실적개선",
        "흑자",
    ]

    has_neg = any(k in text for k in negative)
    has_pos = any(k in text for k in positive)
    if "적자전환" in issue_ctx.profitability_signal:
        return (
            "부정적",
            "흑자에서 적자로 전환된 신호가 확인돼 이익체력과 밸류에이션 할인 확대 가능성을 우선 경계해야 함",
        )
    if "흑자전환" in issue_ctx.profitability_signal:
        has_pos = True

    if has_neg and not has_pos:
        return (
            "부정적",
            (
                "주주가치 희석·회계 신뢰성 훼손·재무 리스크 확대 가능성이 커 보수적 접근이 필요함. "
                f"특히 손익 신호는 '{issue_ctx.profitability_signal}'으로 해석됨"
            ),
        )
    if has_pos and not has_neg:
        return (
            "긍정적",
            "중장기 이익체력 또는 주주환원 기대를 높이는 요인이 상대적으로 우세함",
        )
    return ("중립적", "가치 영향이 상쇄될 수 있어 후속 집행 결과와 분기 실적 확인이 필요함")


def _related_news_summary(
    news_items: list[NewsItem],
    company_name: str,
    issue_ctx: IssueContext,
) -> str:
    if not news_items:
        return (
            "- 관련 보도를 찾지 못했습니다.\n"
            "- 최근 1개월 이내 보도 기준에서 확인 가능한 후속 기사가 제한적입니다."
        )

    lines: list[str] = []
    for news in news_items[:2]:
        source = news.source or "출처 미상"
        date = news.published_at or "날짜 미상"
        summary = _summarize_news_title(news.title, company_name, issue_ctx)
        lines.append(
            f"- [{news.title}]({news.link}) ({source}, {date}) - {summary}"
        )

    if len(news_items) == 1:
        lines.append("- 추가 1건은 최근 보도 부족으로 확인되지 않았습니다.")

    return "\n".join(lines)


def _build_issue_context(item: ScoredDisclosure, news_items: list[NewsItem]) -> IssueContext:
    disclosure = item.disclosure
    text = f"{disclosure.title} {disclosure.description}".replace(" ", "")
    news_title_text = " ".join([n.title for n in news_items]).replace(" ", "")
    corpus = f"{text} {news_title_text}"

    profitability_signal = _profitability_signal(corpus)
    company_plan_signal = _company_plan_signal(corpus)
    core_business_headwind = _core_business_headwind(corpus)

    return IssueContext(
        profitability_signal=profitability_signal,
        company_plan_signal=company_plan_signal,
        core_business_headwind=core_business_headwind,
    )


def _profitability_signal(corpus: str) -> str:
    if "적자전환" in corpus:
        return "적자전환(흑자→적자) 신호가 확인됨 (이익체력 약화 신호)"
    if "흑자전환" in corpus:
        return "흑자전환(적자→흑자) 신호가 확인됨 (수익구조 개선 신호)"
    if any(k in corpus for k in ["영업손실확대", "순손실확대"]):
        return "손실 폭이 확대된 정황이 확인됨"
    if any(k in corpus for k in ["영업이익감소", "순이익감소"]):
        return "이익 감소 신호가 확인됨"
    if any(k in corpus for k in ["영업이익증가", "순이익증가"]):
        return "이익 증가 신호가 확인됨"
    return "명시적 손익 전환 신호는 제한적이며 추가 확인 필요"


def _company_plan_signal(corpus: str) -> str:
    plan_keywords = [
        "신사업",
        "신규사업",
        "사업다각화",
        "사업전환",
        "진출",
        "투자",
        "증설",
        "신제품",
        "고도화",
        "플랫폼",
    ]
    matched = [kw for kw in plan_keywords if kw in corpus]
    if matched:
        return f"{', '.join(list(dict.fromkeys(matched))[:3])} 중심의 확장 계획이 언급됨"
    return "향후 사업 계획은 포괄적으로 제시됐거나 구체성이 제한적임"


def _core_business_headwind(corpus: str) -> str:
    headwind_keywords = [
        "수요둔화",
        "원가상승",
        "판가하락",
        "재고",
        "가동률",
        "경쟁심화",
        "환율",
        "금리",
        "손상차손",
        "충당금",
    ]
    matched = [kw for kw in headwind_keywords if kw in corpus]
    if matched:
        return f"주력 사업에서 {', '.join(list(dict.fromkeys(matched))[:3])} 부담이 포착됨"
    return "주력 사업의 난관은 공시에 정량적으로 충분히 드러나지 않아 후속 설명이 필요함"


def _summarize_news_title(title: str, company_name: str, issue_ctx: IssueContext) -> str:
    compact = title.replace(" ", "")
    if "적자전환" in compact:
        return (
            f"{company_name}의 손익이 흑자에서 적자로 꺾였다는 신호를 확인시켜 "
            "밸류에이션 하향 압력을 점검하게 하는 보도"
        )
    if "흑자전환" in compact:
        return f"{company_name}의 수익구조 개선 가능성을 뒷받침하는 전환 신호 보도"
    if any(k in compact for k in ["유상증자", "전환사채", "신주인수권부사채"]):
        return f"{company_name}의 자금조달/희석 이슈 해석에 직접 연결되는 보도"
    if any(k in compact for k in ["공급계약", "수주"]):
        return f"{company_name}의 수주가 실제 실적으로 연결되는지 추적하는 보도"
    if "주력사업" in issue_ctx.core_business_headwind and "포착됨" in issue_ctx.core_business_headwind:
        return f"{company_name}의 주력 사업 어려움과 연결해 해석할 필요가 있는 보도"
    return f"{company_name} 이슈의 후속 전개를 확인할 수 있는 관련 보도"


def _extract_key_numbers(text: str) -> list[str]:
    pattern = re.compile(r"\d+(?:[.,]\d+)?\s*(?:조|억|백만|천만|만원|원|%)")
    return [match.group(0) for match in pattern.finditer(text)]


def _passes_fact_gate(article: str, selected: list[ScoredDisclosure]) -> bool:
    if not article.strip():
        return False

    if "관련 뉴스 요약" not in article:
        return False

    for item in selected:
        if item.disclosure.company_name not in article:
            return False

    return True
