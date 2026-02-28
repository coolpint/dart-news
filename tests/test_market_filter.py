from pathlib import Path

from datetime import datetime

from dart_digest.market_filter import CompanyUniverse, KospiFilter, MarketFilter
from dart_digest.models import Disclosure


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


def test_market_filter_keeps_kospi_and_kosdaq(tmp_path: Path) -> None:
    csv_path = tmp_path / "companies.csv"
    csv_path.write_text(
        "company_name,ticker,market\n"
        "삼성전자,005930,KOSPI\n"
        "카카오,035720,KOSDAQ\n"
        "비상장테스트,999999,OTC\n",
        encoding="utf-8",
    )

    universe = CompanyUniverse.from_csv(csv_path)
    filt = MarketFilter(universe, {"KOSPI", "KOSDAQ"})

    items = [
        Disclosure(
            company_name="삼성전자",
            title="삼성전자 (유상증자결정)",
            link="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260101000011",
            receipt_no="20260101000011",
            published_at=datetime.utcnow(),
            description="",
        ),
        Disclosure(
            company_name="카카오",
            title="카카오 (단일판매ㆍ공급계약 체결)",
            link="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260101000012",
            receipt_no="20260101000012",
            published_at=datetime.utcnow(),
            description="",
        ),
        Disclosure(
            company_name="비상장테스트",
            title="비상장테스트 (기타경영사항)",
            link="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260101000013",
            receipt_no="20260101000013",
            published_at=datetime.utcnow(),
            description="",
        ),
    ]

    filtered = filt.filter(items)
    assert len(filtered) == 2
    names = {item.company_name for item in filtered}
    assert names == {"삼성전자", "카카오"}
