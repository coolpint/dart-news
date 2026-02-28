from __future__ import annotations

import json
from datetime import datetime

import requests

from dart_digest.config import Settings
from dart_digest.models import ScoredDisclosure


class ArticleWriter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def write(self, selected: list[ScoredDisclosure], run_dt: datetime) -> str:
        if not selected:
            return "오늘은 분석 대상 공시가 없습니다."

        article = ""
        if self.settings.openai_api_key:
            article = self._write_with_openai(selected, run_dt)

        if not article:
            article = self._write_template(selected, run_dt)

        if not _passes_fact_gate(article, selected):
            return self._write_template(selected, run_dt)
        return article

    def _write_with_openai(self, selected: list[ScoredDisclosure], run_dt: datetime) -> str:
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
                    "content": _build_user_prompt(selected, run_dt),
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

    def _write_template(self, selected: list[ScoredDisclosure], run_dt: datetime) -> str:
        headline = _build_headline(selected)
        summary_lines = _build_summary(selected)

        body_blocks: list[str] = []
        for rank, item in enumerate(selected, start=1):
            disclosure = item.disclosure
            body_blocks.append(
                "\n".join(
                    [
                        f"## {rank}. {disclosure.company_name} - {item.event_type}",
                        f"- 공시명: {disclosure.title}",
                        f"- 접수번호: {disclosure.receipt_no}",
                        f"- 링크: {disclosure.link}",
                        f"- 종합 중요도: {item.total_score:.1f} / 100",
                        f"- 핵심 판단 근거: {' / '.join(item.reasons[:3])}",
                        "",
                        "### 왜 중장기적으로 중요한가",
                        _long_term_view(item),
                        "",
                        "### 시나리오 점검",
                        _scenario_view(item),
                        "",
                        "### 후속 체크포인트",
                        _follow_up_view(item),
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


def _build_user_prompt(selected: list[ScoredDisclosure], run_dt: datetime) -> str:
    facts = []
    for idx, item in enumerate(selected, start=1):
        d = item.disclosure
        facts.append(
            {
                "rank": idx,
                "company": d.company_name,
                "title": d.title,
                "receipt_no": d.receipt_no,
                "url": d.link,
                "published_at": d.published_at.isoformat(timespec="seconds"),
                "event_type": item.event_type,
                "score": item.total_score,
                "reasons": item.reasons,
                "description": d.description,
            }
        )

    return (
        f"기준시각: {run_dt.isoformat(timespec='seconds')}\n"
        "아래 공시 후보를 대상으로 심층 기사 작성:\n"
        f"```json\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n```\n"
        "요구사항:\n"
        "1) 제목 1개, 3줄 요약, 본문(사실/해석 분리), 시나리오(Base/Bull/Bear), 후속 체크포인트를 포함\n"
        "2) 접수번호와 원문 링크를 각 기업 섹션에 명시\n"
        "3) 단기 주가 예측 대신 중장기 펀더멘털 관점으로 설명\n"
        "4) 마지막에 투자권유 아님 면책 1문장\n"
    )


def _build_headline(selected: list[ScoredDisclosure]) -> str:
    first = selected[0]
    if len(selected) == 1:
        return f"{first.disclosure.company_name} 공시 심층: {first.event_type}의 중장기 함의"
    second = selected[1]
    return (
        f"오늘의 핵심 공시 2선: {first.disclosure.company_name}·"
        f"{second.disclosure.company_name} 이슈의 구조적 파장"
    )


def _build_summary(selected: list[ScoredDisclosure]) -> list[str]:
    lines = ["## 핵심 요약"]
    for item in selected:
        lines.append(
            f"- {item.disclosure.company_name}: {item.event_type} ({item.total_score:.1f}점)"
        )
    lines.append("- 단기 변동성보다 이익체력·자본구조·거버넌스 변화의 지속성에 초점을 맞춤")
    return lines


def _long_term_view(item: ScoredDisclosure) -> str:
    return (
        f"이번 공시는 `{item.event_type}` 성격으로 분류됐다. "
        f"이벤트 점수({item.event_score:.1f})와 지속성 점수({item.persistence_score:.1f})가 높아 "
        "단기 뉴스플로우를 넘어 중기 실적 추정치 및 밸류에이션 가정 변경 가능성이 있다."
    )


def _scenario_view(item: ScoredDisclosure) -> str:
    return (
        "- Base: 공시 내용이 계획대로 집행되며 기존 추정치가 점진적으로 조정되는 경우\n"
        "- Bull: 집행 속도와 수익성 개선이 동시에 확인되어 멀티플 재평가가 발생하는 경우\n"
        "- Bear: 공시 이행 지연, 비용 확대, 규제/회계 리스크가 재부각되는 경우"
    )


def _follow_up_view(item: ScoredDisclosure) -> str:
    return (
        "1) 후속 정정공시/첨부정정 여부\n"
        "2) 분기 실적 공시에서의 숫자 반영 속도\n"
        "3) 자금조달/부채비율/현금흐름 등 재무지표의 실제 변화"
    )


def _passes_fact_gate(article: str, selected: list[ScoredDisclosure]) -> bool:
    if not article.strip():
        return False

    for item in selected:
        d = item.disclosure
        if d.company_name not in article:
            return False
        if d.receipt_no not in article:
            return False
        if d.link not in article:
            return False

    return True
