"""Unit tests for the pure multi-horizon change computation."""

import pandas as pd
import pytest

from app.services.performance_heatmap import compute_changes


def _series(values, start="2026-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="D"))


def test_positive_trend_changes_are_positive():
    s = _series([100 + i for i in range(70)])  # +1 each day from Jan 1
    ch = compute_changes(s, 2026)
    assert ch["1d"] > 0
    assert ch["1w"] > 0
    assert "ytd" in ch
    # latest = 169, ytd base = 100 -> +69%
    assert ch["ytd"] == pytest.approx((169 / 100 - 1) * 100, abs=0.1)


def test_one_day_change_matches():
    s = _series([100, 102])
    ch = compute_changes(s, 2026)
    assert ch["1d"] == pytest.approx(2.0)


def test_insufficient_data_returns_empty():
    assert compute_changes(_series([100]), 2026) == {}


def test_missing_window_is_omitted():
    s = _series([100, 101, 102])  # only 3 points: 1d yes, 1w/1m/3m no
    ch = compute_changes(s, 2026)
    assert "1d" in ch
    assert "1m" not in ch
