from datetime import datetime
from pathlib import Path

from dart_digest.article_writer import ArticleWriter
from dart_digest.config import Settings
from dart_digest.models import Disclosure, ScoredDisclosure


def test_template_excludes_receipt_no_and_scenario() -> None:
    settings = Settings(
        rss_url="https://dart.fss.or.kr/api/todayRSS.xml",
        db_path=Path("/tmp/dart_test.db"),
        company_map_path=Path("/tmp/company_map.csv"),
        target_markets=("KOSPI", "KOSDAQ"),
        dart_api_key=None,
        timezone="Asia/Seoul",
        top_n_max=2,
        second_pick_min_score=78.0,
        second_pick_min_gap=6.0,
        openai_api_key=None,
        openai_model="gpt-4.1-mini",
        slack_webhook_url=None,
        slack_channel=None,
        notify_on_skip=True,
        require_slack_webhook=False,
        dry_run=True,
    )

    disclosure = Disclosure(
        company_name="테스트전자",
        title="테스트전자 (유상증자결정)",
        link="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260227000001",
        receipt_no="20260227000001",
        published_at=datetime(2026, 2, 27, 10, 0, 0),
        description="1.2조원 규모 자금조달",
    )
    scored = ScoredDisclosure(
        disclosure=disclosure,
        market="KOSPI",
        event_type="지배구조/자본변동",
        event_score=95.0,
        financial_score=90.0,
        persistence_score=88.0,
        confidence_score=80.0,
        market_bonus=5.0,
        total_score=90.4,
        reasons=["자본구조 변화는 희석/레버리지/주주가치에 중장기 영향을 줄 가능성이 큼"],
    )

    writer = ArticleWriter(settings)
    article = writer._write_template([scored], datetime(2026, 2, 27, 18, 10, 0), {})

    assert "접수번호" not in article
    assert "시나리오 점검" not in article
    assert "관련 뉴스 요약" in article
    assert "투자자 관점 해석" in article
