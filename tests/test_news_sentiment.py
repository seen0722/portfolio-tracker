"""Unit tests for the pure news-sentiment signal."""

from app.domain.signals import BEARISH, BULLISH, GREEN, NEUTRAL, RED, UNKNOWN
from app.signals.news_sentiment import compute_sentiment_signal


def test_no_headlines_is_unknown():
    sig = compute_sentiment_signal("NVDA", [], "2026-06-19")
    assert sig.light == UNKNOWN
    assert sig.signal_id == "news_sentiment"


def test_positive_headlines_are_bullish():
    headlines = ["NVDA beats earnings, stock surges to record high", "Analysts upgrade on strong growth"]
    sig = compute_sentiment_signal("NVDA", headlines, "2026-06-19")
    assert sig.direction == BULLISH
    assert sig.score > 0


def test_negative_headlines_are_bearish():
    headlines = ["NVDA misses, shares plunge on weak guidance", "Downgrade amid lawsuit and probe"]
    sig = compute_sentiment_signal("NVDA", headlines, "2026-06-19")
    assert sig.direction == BEARISH
    assert sig.score < 0


def test_neutral_headlines_have_no_direction():
    headlines = ["NVDA to host annual conference next week", "Company announces new office location"]
    sig = compute_sentiment_signal("NVDA", headlines, "2026-06-19")
    assert sig.direction == NEUTRAL
    assert sig.light == GREEN
