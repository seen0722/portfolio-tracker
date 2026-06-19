"""Unit tests for the pure NAV reconstruction transform."""

import pandas as pd
import pytest

from app.services.nav_service import reconstruct_nav_series


def _closes():
    idx = pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-04"])
    return pd.DataFrame({"NVDA": [100.0, 110.0, 120.0]}, index=idx)


def test_values_usd_holding_at_each_close_plus_cash():
    holdings = [("NVDA", 10.0, "USD")]
    df = reconstruct_nav_series(holdings, _closes(), cash_usd=500.0, fx_usdtwd=32.0)
    assert list(df["total_usd"]) == pytest.approx([1500, 1600, 1700])  # 10*close + 500
    assert df["total_twd"].iloc[0] == pytest.approx(1500 * 32.0)
    assert df["date"].tolist() == ["2026-01-02", "2026-01-03", "2026-01-04"]


def test_daily_return_is_computed():
    holdings = [("NVDA", 10.0, "USD")]
    df = reconstruct_nav_series(holdings, _closes(), cash_usd=0.0, fx_usdtwd=32.0)
    # 1000 -> 1100 -> 1200 ; first row 0, then +10%, then +9.09%
    assert df["daily_return_pct"].iloc[0] == pytest.approx(0.0)
    assert df["daily_return_pct"].iloc[1] == pytest.approx(10.0)
    assert df["daily_return_pct"].iloc[2] == pytest.approx(100.0 / 11.0)


def test_twd_holding_converted_to_usd():
    idx = pd.to_datetime(["2026-01-02"])
    closes = pd.DataFrame({"2330.TW": [640.0]}, index=idx)
    holdings = [("2330.TW", 100.0, "TWD")]
    df = reconstruct_nav_series(holdings, closes, cash_usd=0.0, fx_usdtwd=32.0)
    # 100 * 640 TWD / 32 = 2000 USD
    assert df["total_usd"].iloc[0] == pytest.approx(2000.0)


def test_empty_closes_returns_empty_frame():
    df = reconstruct_nav_series([("NVDA", 1.0, "USD")], pd.DataFrame(), 0.0, 32.0)
    assert df.empty


def test_symbol_missing_from_closes_is_skipped():
    holdings = [("NVDA", 10.0, "USD"), ("MISSING", 5.0, "USD")]
    df = reconstruct_nav_series(holdings, _closes(), cash_usd=0.0, fx_usdtwd=32.0)
    assert df["total_usd"].iloc[0] == pytest.approx(1000.0)  # only NVDA counted
