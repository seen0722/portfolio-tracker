"""Report notifiers. Telegram via plain requests (no heavy SDK); a Log fallback
that always "succeeds" so the daily job never fails when no channel is configured.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class LogNotifier:
    """Always-available fallback: writes the report to the log."""

    name = "log"

    def send(self, title: str, text: str) -> bool:
        logger.info("[REPORT] %s\n%s", title, text)
        return True


class TelegramNotifier:
    """Push a report to a Telegram chat via the Bot API."""

    name = "telegram"

    def __init__(self, token: str, chat_id: str, timeout: int = 15) -> None:
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout

    def send(self, title: str, text: str) -> bool:
        import requests

        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": f"{title}\n\n{text}"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return True
        except Exception as exc:  # never let a push failure crash the job
            logger.warning("Telegram push failed: %s", exc)
            return False
