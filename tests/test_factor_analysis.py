"""Unit tests for the pure factor-correlation functions."""

import pandas as pd

from app.services.factor_analysis import compute_sensitivity, overlay_series


def _series(values, start="2026-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="D"))


def _levels(returns, start=100.0):
    out = [start]
    for r in returns:
        out.append(out[-1] * (1 + r))
    return out


_RETURNS = [0.02, -0.01, 0.03, -0.02, 0.025, -0.015, 0.02, -0.01, 0.03, -0.02, 0.01]


def test_positive_correlation_detected():
    tgt = _series(_levels(_RETURNS))
    fac = _series(_levels(_RETURNS))  # identical returns -> corr 1
    rows = compute_sensitivity(tgt, {"F": fac}, min_points=5)
    assert rows[0]["corr"] > 0.95


def test_negative_correlation_detected():
    tgt = _series(_levels(_RETURNS))
    fac = _series(_levels([-r for r in _RETURNS]))  # mirrored returns -> corr -1
    rows = compute_sensitivity(tgt, {"F": fac}, min_points=5)
    assert rows[0]["corr"] < -0.95


def test_insufficient_points_corr_none():
    tgt = _series([100, 101, 102])
    fac = _series([10, 11, 12])
    rows = compute_sensitivity(tgt, {"F": fac}, min_points=10)
    assert rows[0]["corr"] is None


def test_sorted_by_abs_corr_strongest_first():
    tgt = _series(_levels(_RETURNS))
    strong = _series(_levels([-r for r in _RETURNS]))
    weak = _series([5, 5.05, 5.0, 5.05, 5.0, 5.05, 5.0, 5.05, 5.0, 5.05, 5.0, 5.05])
    rows = compute_sensitivity(tgt, {"weak": weak, "strong": strong}, min_points=5)
    assert rows[0]["key"] == "strong"


def test_overlay_rebases_to_pct_from_start():
    tgt = _series([100, 110, 120])
    fac = _series([10, 11, 9])
    ov = overlay_series(tgt, fac)
    assert ov["target_pct"] == [0.0, 10.0, 20.0]
    assert ov["factor_pct"][0] == 0.0
    assert ov["dates"][0] == "2026-01-01"
    assert len(ov["dates"]) == 3
