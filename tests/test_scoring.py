from datetime import datetime

from dart_digest.models import Disclosure
from dart_digest.scoring import score_disclosure


def _build_disclosure(title: str, description: str) -> Disclosure:
    return Disclosure(
        company_name="테스트회사",
        title=title,
        link="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260101000003",
        receipt_no="20260101000003",
        published_at=datetime.utcnow(),
        description=description,
    )


def test_capital_event_scores_high() -> None:
    disclosure = _build_disclosure(
        "테스트회사 (유상증자결정)",
        "자금조달 규모는 1.2조원이며 기존 주식 대비 20% 수준",
    )
    scored = score_disclosure(disclosure)

    assert scored.event_type == "지배구조/자본변동"
    assert scored.total_score >= 80


def test_generic_event_scores_lower() -> None:
    disclosure = _build_disclosure(
        "테스트회사 (임시주주총회 소집결의)",
        "상정 안건은 정관 변경",
    )
    scored = score_disclosure(disclosure)

    assert scored.total_score < 80
