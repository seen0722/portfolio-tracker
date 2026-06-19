"""Unit tests for the capex monitor signal logic and yfinance parsing."""

from __future__ import annotations

from datetime import date
from typing import List

import pandas as pd
import pytest

from app.infrastructure import capex_monitor
from app.infrastructure.capex_monitor import (
    CapexMonitor,
    CapexQuarter,
    compute_capex_signal,
)

# Newest-first quarter periods used to build synthetic histories.
_PERIODS = [
    "2026-03-31",
    "2025-12-31",
    "2025-09-30",
    "2025-06-30",
    "2025-03-31",
    "2024-12-31",
    "2024-09-30",
]


def make_quarters(values: List[float]) -> List[CapexQuarter]:
    """Build quarters from capex values given newest-first."""
    return [CapexQuarter(period=_PERIODS[i], capex=v) for i, v in enumerate(values)]


# --- compute_capex_signal: traffic-light classification ---------------------


def test_accelerating_growth_is_green():
    # YoY: y0=(36-18)/18=100%, y1=(28-16)/16=75%  -> accelerating
    signal = compute_capex_signal("X", make_quarters([36, 28, 24, 22, 18, 16, 12]))
    assert signal.trend == "accelerating"
    assert signal.light == "green"
    assert signal.yoy_growth_pct == 100.0


def test_single_quarter_deceleration_is_yellow():
    # y0=50%, y1=80%, y2=80%  -> decelerated once only
    signal = compute_capex_signal("X", make_quarters([30, 36, 36, 22, 20, 20, 20]))
    assert signal.trend == "decelerating"
    assert signal.light == "yellow"


def test_two_quarter_deceleration_is_red():
    # y0=20%, y1=50%, y2=80%  -> decelerating two quarters in a row
    signal = compute_capex_signal("X", make_quarters([24, 30, 36, 22, 20, 20, 20]))
    assert signal.trend == "decelerating"
    assert signal.light == "red"


def test_negative_yoy_is_red():
    # y0=(15-20)/20=-25%
    signal = compute_capex_signal("X", make_quarters([15, 16, 17, 18, 20]))
    assert signal.light == "red"
    assert signal.yoy_growth_pct == -25.0


def test_insufficient_history_is_unknown():
    signal = compute_capex_signal("X", make_quarters([30, 28, 26]))
    assert signal.light == "unknown"
    assert signal.yoy_growth_pct is None


def test_empty_history_is_unknown():
    signal = compute_capex_signal("X", [])
    assert signal.light == "unknown"
    assert signal.latest_period is None
    assert signal.note == "無 capex 資料"


def test_single_yoy_point_is_unknown():
    # 5 quarters -> only y0 computable, no y1 to compare against
    signal = compute_capex_signal("X", make_quarters([30, 28, 26, 24, 20]))
    assert signal.yoy_growth_pct == 50.0
    assert signal.light == "unknown"


def test_qoq_and_latest_fields():
    signal = compute_capex_signal(
        "X", make_quarters([36, 30, 24, 22, 18, 16, 12]), next_earnings="2026-07-24"
    )
    assert signal.latest_period == "2026-03-31"
    assert signal.latest_capex == 36
    assert signal.qoq_growth_pct == 20.0  # (36-30)/30
    assert signal.next_earnings == "2026-07-24"


def test_unsorted_input_is_ordered_internally():
    quarters = make_quarters([36, 28, 24, 22, 18, 16, 12])
    shuffled = [quarters[3], quarters[0], quarters[5], quarters[1], quarters[2], quarters[4], quarters[6]]
    signal = compute_capex_signal("X", shuffled)
    assert signal.latest_period == "2026-03-31"
    assert signal.latest_capex == 36


# --- CapexMonitor: yfinance parsing & caching -------------------------------


class _FakeTicker:
    """Minimal stand-in for yfinance.Ticker."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    @property
    def quarterly_cashflow(self) -> pd.DataFrame:
        index = ["Free Cash Flow", "Capital Expenditure"]
        columns = [pd.Timestamp("2026-03-31"), pd.Timestamp("2025-12-31")]
        # Capex reported as negative outflow; monitor must take the magnitude.
        data = [[1.0, 2.0], [-35.7e9, -27.9e9]]
        return pd.DataFrame(data, index=index, columns=columns)

    @property
    def calendar(self) -> dict:
        return {"Earnings Date": [date(2026, 7, 24)]}


    def get_info(self) -> dict:
        return {"financialCurrency": "USD"}


def test_parse_capex_takes_magnitude_and_sorts(monkeypatch):
    monkeypatch.setattr(capex_monitor.yf, "Ticker", _FakeTicker)
    monitor = CapexMonitor()
    quarters, next_earnings, currency = monitor._fetch("GOOG")
    assert [q.period for q in quarters] == ["2026-03-31", "2025-12-31"]
    assert quarters[0].capex == pytest.approx(35.7e9)  # positive magnitude
    assert next_earnings == "2026-07-24"
    assert currency == "USD"


def test_fetch_degrades_gracefully_on_error(monkeypatch):
    def _boom(_symbol):
        raise RuntimeError("network down")

    monkeypatch.setattr(capex_monitor.yf, "Ticker", _boom)
    monitor = CapexMonitor()
    quarters, next_earnings, currency = monitor._fetch("GOOG")
    assert quarters == []
    assert next_earnings is None
    assert currency is None


def test_get_signal_uses_cache(monkeypatch):
    calls = {"count": 0}

    def fake_fetch(_symbol):
        calls["count"] += 1
        return make_quarters([36, 28, 24, 22, 18, 16, 12]), "2026-07-24", "USD"

    monitor = CapexMonitor()
    monkeypatch.setattr(monitor, "_fetch", fake_fetch)

    first = monitor.get_signal("GOOG")
    second = monitor.get_signal("GOOG")
    assert calls["count"] == 1  # second call served from cache
    assert first == second
    assert first.light == "green"
    assert first.currency == "USD"


def test_offline_returns_unknown_without_fetching():
    monitor = CapexMonitor(allow_online=False)
    signal = monitor.get_signal("GOOG")
    assert signal.light == "unknown"


def test_get_signals_parallel(monkeypatch):
    def fake_fetch(symbol):
        return make_quarters([36, 28, 24, 22, 18, 16, 12]), None, "USD"

    monitor = CapexMonitor()
    monkeypatch.setattr(monitor, "_fetch", fake_fetch)
    signals = monitor.get_signals(["AMZN", "GOOGL", "MSFT"])
    assert set(signals) == {"AMZN", "GOOGL", "MSFT"}
    assert all(s.light == "green" for s in signals.values())
