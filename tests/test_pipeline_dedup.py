from pathlib import Path

import dart_digest.pipeline as pipeline_module
from dart_digest.config import Settings
from dart_digest.pipeline import DigestPipeline


def test_pipeline_skips_already_processed_disclosures(tmp_path: Path) -> None:
    csv_path = tmp_path / "companies.csv"
    csv_path.write_text(
        "company_name,ticker,market\n"
        "삼성전자,005930,KOSPI\n"
        "카카오,035720,KOSDAQ\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "digest.db"

    settings = Settings(
        rss_url="https://example.com/rss.xml",
        db_path=db_path,
        company_map_path=csv_path,
        target_markets=("KOSPI", "KOSDAQ"),
        timezone="Asia/Seoul",
        top_n_max=2,
        second_pick_min_score=70.0,
        second_pick_min_gap=15.0,
        openai_api_key=None,
        openai_model="gpt-4.1-mini",
        slack_webhook_url=None,
        slack_channel=None,
        dry_run=True,
    )

    sample_xml = """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<rss><channel>
  <item>
    <title>삼성전자 (유상증자결정)</title>
    <link>https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260228000001</link>
    <description>1.2조원 규모 자금 조달, 신주 발행비율 20%</description>
    <pubDate>Sat, 28 Feb 2026 09:00:00 +0900</pubDate>
  </item>
  <item>
    <title>카카오 (단일판매ㆍ공급계약 체결)</title>
    <link>https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260228000002</link>
    <description>500억원 규모 계약</description>
    <pubDate>Sat, 28 Feb 2026 09:10:00 +0900</pubDate>
  </item>
</channel></rss>"""

    original_fetch = pipeline_module.fetch_today_rss
    pipeline_module.fetch_today_rss = lambda _url: sample_xml
    try:
        pipe = DigestPipeline(settings)
        first = pipe.run(force=False)
        assert first.status == "completed"

        second = pipe.run(force=False)
        assert second.status == "skipped"
        assert second.message == "No new disclosures after deduplication."
    finally:
        pipeline_module.fetch_today_rss = original_fetch
