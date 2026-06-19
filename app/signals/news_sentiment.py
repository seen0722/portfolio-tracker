"""Lightweight news-sentiment signal — transparent lexicon over recent headlines.

A deliberately simple, dependency-free baseline (no finBERT/torch install): it
counts positive/negative finance terms in recent headlines. `compute_sentiment_signal`
is pure and tested; `_fetch` is the yfinance seam. Degrades to UNKNOWN when no
news is available. finBERT can later swap in behind the same Signal contract.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import List, Sequence, Tuple

import yfinance as yf

from app.domain.signals import (
    BEARISH,
    BULLISH,
    GREEN,
    NEUTRAL,
    RED,
    SignalOutput,
    UNKNOWN,
    YELLOW,
)

logger = logging.getLogger(__name__)

SIGNAL_ID = "news_sentiment"
VERSION = 1
MAX_HEADLINES = 15

POSITIVE = {
    "beat", "beats", "surge", "surges", "record", "upgrade", "upgrades", "growth",
    "strong", "rally", "rallies", "gain", "gains", "jumps", "soars", "outperform",
    "bullish", "raise", "raises", "tops", "wins", "profit", "boost", "rebound", "high",
}
NEGATIVE = {
    "miss", "misses", "plunge", "plunges", "cut", "cuts", "downgrade", "downgrades",
    "weak", "fall", "falls", "drop", "drops", "slumps", "lawsuit", "probe", "warn",
    "warns", "bearish", "loss", "losses", "decline", "slash", "fraud", "recall", "low",
}

_WORD = re.compile(r"[a-z']+")


def compute_sentiment_signal(
    symbol: str, headlines: Sequence[str], as_of: str
) -> SignalOutput:
    if not headlines:
        return SignalOutput(symbol, SIGNAL_ID, VERSION, 0.0, UNKNOWN, NEUTRAL, 0.0, "無近期新聞", as_of)

    pos = neg = 0
    for headline in headlines:
        words = set(_WORD.findall(headline.lower()))
        pos += len(words & POSITIVE)
        neg += len(words & NEGATIVE)

    total = pos + neg
    if total == 0:
        return SignalOutput(
            symbol, SIGNAL_ID, VERSION, 0.0, GREEN, NEUTRAL, 0.0,
            f"{len(headlines)} 則新聞，情緒中性", as_of,
        )

    net = (pos - neg) / total  # [-1, 1]
    if net > 0.2:
        light, direction = GREEN, BULLISH
    elif net < -0.2:
        light, direction = (RED if net <= -0.5 else YELLOW), BEARISH
    else:
        light, direction = GREEN, NEUTRAL

    evidence = f"{len(headlines)} 則新聞，正面 {pos}／負面 {neg}"
    return SignalOutput(symbol, SIGNAL_ID, VERSION, round(net, 3), light, direction, round(net, 2), evidence, as_of)


class NewsSentimentSignal:
    signal_id = SIGNAL_ID
    version = VERSION

    def __init__(self, allow_online: bool = True) -> None:
        self.allow_online = allow_online

    def for_symbol(self, symbol: str) -> SignalOutput:
        headlines, as_of = self._fetch(symbol)
        return compute_sentiment_signal(symbol, headlines, as_of)

    def _fetch(self, symbol: str) -> Tuple[List[str], str]:
        today = date.today().isoformat()
        if not self.allow_online:
            return [], today
        try:
            news = yf.Ticker(symbol).news or []
            headlines: List[str] = []
            for item in news[:MAX_HEADLINES]:
                title = item.get("title")
                if not title and isinstance(item.get("content"), dict):
                    title = item["content"].get("title")
                if title:
                    headlines.append(str(title))
            return headlines, today
        except Exception as exc:  # degrade gracefully
            logger.warning("News fetch failed for %s: %s", symbol, exc)
            return [], today
