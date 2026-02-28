from pathlib import Path

from dart_digest.market_filter import CompanyUniverse, KospiFilter
from dart_digest.models import Disclosure
from datetime import datetime


def test_kospi_filter_only_keeps_kospi(tmp_path: Path) -> None:
    csv_path = tmp_path / "companies.csv"
    csv_path.write_text(
        "company_name,ticker,market\n"
        "삼성전자,005930,KOSPI\n"
        "카카오,035720,KOSDAQ\n",
        encoding="utf-8",
    )

    universe = CompanyUniverse.from_csv(csv_path)
    filt = KospiFilter(universe)

    items = [
        Disclosure(
            company_name="삼성전자",
            title="삼성전자 (단일판매ㆍ공급계약 체결)",
            link="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260101000001",
            receipt_no="20260101000001",
            published_at=datetime.utcnow(),
            description="",
        ),
        Disclosure(
            company_name="카카오",
            title="카카오 (단일판매ㆍ공급계약 체결)",
            link="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260101000002",
            receipt_no="20260101000002",
            published_at=datetime.utcnow(),
            description="",
        ),
    ]

    filtered = filt.filter(items)
    assert len(filtered) == 1
    assert filtered[0].company_name == "삼성전자"
