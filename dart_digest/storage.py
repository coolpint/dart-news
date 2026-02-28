from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from dart_digest.models import DailySelection, ScoredDisclosure


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_disclosures (
                    receipt_no TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    total_score REAL NOT NULL,
                    published_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS published_reports (
                    report_date TEXT PRIMARY KEY,
                    receipt_nos TEXT NOT NULL,
                    article TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def is_processed(self, receipt_no: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_disclosures WHERE receipt_no = ?",
                (receipt_no,),
            ).fetchone()
            return row is not None

    def mark_processed(self, scored: ScoredDisclosure) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO processed_disclosures
                (receipt_no, company_name, title, event_type, total_score, published_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(receipt_no) DO UPDATE SET
                    company_name = excluded.company_name,
                    title = excluded.title,
                    event_type = excluded.event_type,
                    total_score = excluded.total_score,
                    published_at = excluded.published_at,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    scored.disclosure.receipt_no,
                    scored.disclosure.company_name,
                    scored.disclosure.title,
                    scored.event_type,
                    scored.total_score,
                    scored.disclosure.published_at.isoformat(timespec="seconds"),
                    now,
                ),
            )
            conn.commit()

    def report_exists(self, report_date: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM published_reports WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            return row is not None

    def save_report(self, selection: DailySelection) -> None:
        report_date = selection.run_date.isoformat(timespec="seconds")
        receipt_nos = [item.disclosure.receipt_no for item in selection.selected]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO published_reports (report_date, receipt_nos, article, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_date) DO UPDATE SET
                    receipt_nos = excluded.receipt_nos,
                    article = excluded.article,
                    created_at = excluded.created_at
                """,
                (
                    report_date,
                    json.dumps(receipt_nos, ensure_ascii=False),
                    selection.generated_article,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
