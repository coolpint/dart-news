from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from dart_digest.article_writer import ArticleWriter
from dart_digest.config import Settings
from dart_digest.dart_client import fetch_today_rss, parse_disclosures
from dart_digest.market_filter import CompanyUniverse, KospiFilter
from dart_digest.models import DailySelection, ScoredDisclosure
from dart_digest.scoring import score_disclosures
from dart_digest.slack_client import SlackPublisher
from dart_digest.storage import Storage


@dataclass
class PipelineResult:
    status: str
    message: str
    selection: DailySelection | None = None


class DigestPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage = Storage(settings.db_path)
        self.universe = CompanyUniverse.from_csv(settings.company_map_path)
        self.market_filter = KospiFilter(self.universe)
        self.writer = ArticleWriter(settings)
        self.publisher = SlackPublisher(
            webhook_url=settings.slack_webhook_url,
            channel=settings.slack_channel,
        )

    def run(self, force: bool = False) -> PipelineResult:
        run_dt = datetime.now(ZoneInfo(self.settings.timezone)).replace(tzinfo=None)
        report_date = run_dt.date().isoformat()

        if not force and self.storage.report_exists(report_date):
            return PipelineResult(
                status="skipped",
                message=f"{report_date} report already exists; skipping.",
            )

        rss_xml = fetch_today_rss(self.settings.rss_url)
        disclosures = parse_disclosures(rss_xml)
        kospi_disclosures = self.market_filter.filter(disclosures)

        if not kospi_disclosures:
            return PipelineResult(status="skipped", message="No KOSPI disclosures found.")

        scored = score_disclosures(kospi_disclosures)
        selected = self._pick_top(scored)

        if not selected:
            return PipelineResult(
                status="skipped",
                message="No disclosure passed the importance threshold.",
            )

        article = self.writer.write(selected, run_dt)
        selection = DailySelection(
            run_date=run_dt,
            selected=selected,
            generated_article=article,
        )

        self.storage.save_report(selection)
        for item in scored:
            self.storage.mark_processed(item)

        if not self.settings.dry_run:
            sent = self.publisher.publish(article, selected, run_dt)
            if not sent:
                return PipelineResult(
                    status="completed",
                    message=(
                        "Report generated but not sent to Slack "
                        "(missing SLACK_WEBHOOK_URL)."
                    ),
                    selection=selection,
                )

        return PipelineResult(
            status="completed",
            message=f"Generated report with {len(selected)} disclosure(s).",
            selection=selection,
        )

    def _pick_top(self, scored: list[ScoredDisclosure]) -> list[ScoredDisclosure]:
        if not scored:
            return []

        ranked = sorted(
            scored,
            key=lambda x: (x.total_score, x.disclosure.published_at),
            reverse=True,
        )

        primary = ranked[0]
        if primary.total_score < 60.0:
            return []

        selected = [primary]

        if self.settings.top_n_max < 2 or len(ranked) < 2:
            return selected

        secondary = ranked[1]
        score_gap = primary.total_score - secondary.total_score

        if secondary.total_score < self.settings.second_pick_min_score:
            return selected

        if score_gap > self.settings.second_pick_min_gap:
            return selected

        if secondary.event_type == primary.event_type:
            return selected

        selected.append(secondary)
        return selected
