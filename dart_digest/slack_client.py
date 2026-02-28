from __future__ import annotations

from datetime import datetime

import requests

from dart_digest.models import ScoredDisclosure


class SlackPublisher:
    def __init__(self, webhook_url: str | None, channel: str | None = None) -> None:
        self.webhook_url = webhook_url
        self.channel = channel

    def publish(self, article: str, selected: list[ScoredDisclosure], run_dt: datetime) -> bool:
        if not self.webhook_url:
            return False

        intro = self._intro(selected, run_dt)
        chunks = _chunk_text(article, size=3200)

        # First message: intro and first chunk.
        all_chunks = [intro + "\n\n" + chunks[0]] + chunks[1:]
        for idx, chunk in enumerate(all_chunks, start=1):
            payload = {"text": chunk}
            if self.channel:
                payload["channel"] = self.channel

            response = requests.post(self.webhook_url, json=payload, timeout=15)
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Slack publish failed at chunk {idx}: "
                    f"{response.status_code} {response.text[:200]}"
                )

        return True

    def publish_text(self, text: str) -> bool:
        if not self.webhook_url:
            return False

        payload = {"text": text}
        if self.channel:
            payload["channel"] = self.channel

        response = requests.post(self.webhook_url, json=payload, timeout=15)
        if response.status_code >= 400:
            raise RuntimeError(
                f"Slack publish failed: {response.status_code} {response.text[:200]}"
            )
        return True

    @staticmethod
    def _intro(selected: list[ScoredDisclosure], run_dt: datetime) -> str:
        picked = ", ".join(
            [f"{item.disclosure.company_name}({item.total_score:.1f})" for item in selected]
        )
        return (
            f"[DART 심층 리포트] {run_dt.strftime('%Y-%m-%d')}\n"
            f"선정 공시: {picked}"
        )


def _chunk_text(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            # Prefer splitting on newline to keep readability.
            split = text.rfind("\n", start, end)
            if split > start + 200:
                end = split
        chunks.append(text[start:end].strip())
        start = end
    return [chunk for chunk in chunks if chunk]
