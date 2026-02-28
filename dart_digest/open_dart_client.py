from __future__ import annotations

from datetime import datetime

import requests

from dart_digest.models import Disclosure


API_URL = "https://opendart.fss.or.kr/api/list.json"
MARKET_TO_CORP_CLS = {
    "KOSPI": "Y",
    "KOSDAQ": "K",
}


def fetch_disclosures_by_date(
    target_date: str,
    api_key: str,
    target_markets: tuple[str, ...],
    timeout_seconds: int = 20,
) -> list[Disclosure]:
    if not (len(target_date) == 8 and target_date.isdigit()):
        raise ValueError("target_date must be YYYYMMDD")

    corp_classes = [
        MARKET_TO_CORP_CLS[m] for m in target_markets if m in MARKET_TO_CORP_CLS
    ]
    corp_classes = list(dict.fromkeys(corp_classes))
    if not corp_classes:
        return []

    collected: dict[str, Disclosure] = {}

    for corp_cls in corp_classes:
        page_no = 1
        while True:
            payload = {
                "crtfc_key": api_key,
                "bgn_de": target_date,
                "end_de": target_date,
                "corp_cls": corp_cls,
                "sort": "date",
                "sort_m": "desc",
                "page_no": page_no,
                "page_count": 100,
            }
            response = requests.get(API_URL, params=payload, timeout=timeout_seconds)
            response.raise_for_status()
            data = response.json()

            status = str(data.get("status", ""))
            if status == "013":
                break
            if status != "000":
                message = data.get("message", "Unknown OpenDART error")
                raise RuntimeError(f"OpenDART API error {status}: {message}")

            items = data.get("list") or []
            for item in items:
                receipt_no = str(item.get("rcept_no") or "").strip()
                if not receipt_no:
                    continue

                company_name = str(item.get("corp_name") or "").strip()
                title = str(item.get("report_nm") or "").strip()
                rcept_dt = str(item.get("rcept_dt") or target_date).strip()
                published_at = _parse_rcept_dt(rcept_dt)

                filler = str(item.get("flr_nm") or "").strip()
                remark = str(item.get("rm") or "").strip()
                description = " / ".join(x for x in [filler, remark] if x)

                collected[receipt_no] = Disclosure(
                    company_name=company_name,
                    title=f"{company_name} ({title})" if company_name and title else title,
                    link=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}",
                    receipt_no=receipt_no,
                    published_at=published_at,
                    description=description,
                    raw={"source": "opendart", "corp_cls": corp_cls},
                )

            total_page = int(data.get("total_page", 1) or 1)
            if page_no >= total_page:
                break
            page_no += 1

    return sorted(
        collected.values(),
        key=lambda x: (x.published_at, x.receipt_no),
        reverse=True,
    )


def _parse_rcept_dt(raw: str) -> datetime:
    if len(raw) == 8 and raw.isdigit():
        return datetime.strptime(raw, "%Y%m%d")
    return datetime.utcnow()
