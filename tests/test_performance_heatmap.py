"""Unit tests for the pure multi-horizon change computation."""

from datetime import date

import pandas as pd
import pytest

from app.services.performance_heatmap import compute_changes


def _series(values, start="2026-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="D"))


def test_positive_trend_changes_are_positive():
    s = _series([100 + i for i in range(70)])  # +1 each day from Jan 1
    ch = compute_changes(s, date(2026, 3, 11))
    assert ch["1d"] > 0
    assert ch["1w"] > 0
    assert "ytd" in ch and "qtd" in ch
    # latest = 169, ytd base = 100 -> +69%
    assert ch["ytd"] == pytest.approx((169 / 100 - 1) * 100, abs=0.1)


def test_one_day_change_matches():
    s = _series([100, 102])
    ch = compute_changes(s, date(2026, 1, 2))
    assert ch["1d"] == pytest.approx(2.0)


def test_insufficient_data_returns_empty():
    assert compute_changes(_series([100]), date(2026, 1, 1)) == {}


def test_missing_window_is_omitted():
    s = _series([100, 101, 102])  # only 3 points: 1d yes, 1y no
    ch = compute_changes(s, date(2026, 1, 3))
    assert "1d" in ch
    assert "1y" not in ch


class _FakeHist:
    def get_closes(self, tickers, period):
        idx = pd.date_range("2026-01-01", periods=70, freq="D")
        return pd.DataFrame({t: [100 + i for i in range(70)] for t in tickers}, index=idx)


def test_build_includes_close_value_and_changes():
    from app.services.performance_heatmap import PerformanceHeatmap

    groups = PerformanceHeatmap(_FakeHist(), None).build(holdings=["NVDA"])
    rows = [r for g in groups for r in g["rows"]]
    assert rows and all("close" in r and "changes" in r for r in rows)
    nvda = next(r for r in rows if r["label"] == "NVDA")
    assert nvda["close"] == 169.0  # latest of 100..169
    assert "ytd" in nvda["changes"]

