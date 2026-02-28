from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


def _get_csv_list(name: str, default: str) -> tuple[str, ...]:
    raw = os.getenv(name, default)
    items = [item.strip().upper() for item in raw.split(",") if item.strip()]
    return tuple(dict.fromkeys(items))


@dataclass
class Settings:
    rss_url: str
    db_path: Path
    company_map_path: Path
    target_markets: tuple[str, ...]
    timezone: str
    top_n_max: int
    second_pick_min_score: float
    second_pick_min_gap: float
    openai_api_key: str | None
    openai_model: str
    slack_webhook_url: str | None
    slack_channel: str | None
    notify_on_skip: bool
    dry_run: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            rss_url=os.getenv("DART_RSS_URL", "https://dart.fss.or.kr/api/todayRSS.xml"),
            db_path=Path(os.getenv("DART_DB_PATH", str(ROOT_DIR / "data" / "dart_digest.db"))),
            company_map_path=Path(
                os.getenv(
                    "DART_COMPANY_MAP_PATH",
                    str(ROOT_DIR / "data" / "kospi_companies_sample.csv"),
                )
            ),
            target_markets=_get_csv_list("DART_TARGET_MARKETS", "KOSPI,KOSDAQ")
            or ("KOSPI", "KOSDAQ"),
            timezone=os.getenv("DART_TIMEZONE", "Asia/Seoul"),
            top_n_max=max(1, min(2, _get_int("DART_TOP_N_MAX", 2))),
            second_pick_min_score=_get_float("DART_SECOND_PICK_MIN_SCORE", 78.0),
            second_pick_min_gap=_get_float("DART_SECOND_PICK_MIN_GAP", 6.0),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
            slack_channel=os.getenv("SLACK_CHANNEL"),
            notify_on_skip=_get_bool("DART_NOTIFY_ON_SKIP", True),
            dry_run=_get_bool("DRY_RUN", False),
        )
