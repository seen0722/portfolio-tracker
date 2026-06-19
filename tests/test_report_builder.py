"""Unit tests for the pure daily-report builder."""

from app.domain.advice import ADD, DISCLAIMER, OpinionCard
from app.domain.models import PortfolioResult, PositionBreakdown, Totals
from app.services.report_builder import build_report


def _result():
    totals = Totals()
    totals.add(1500.0, 48000.0, 1000.0, 32000.0)  # stock
    totals.add(100.0, 3200.0, 100.0, 3200.0)  # cash
    pos = PositionBreakdown(
        name="NVDA", category="stock", value_usd=1500.0, value_twd=48000.0,
        portfolio_pct=80.0, quantity=10, unit_price=150.0, price_currency="USD",
        average_cost=100.0, total_cost_usd=1000.0, total_cost_twd=32000.0,
        unrealized_pl_usd=500.0, unrealized_pl_twd=16000.0, roi_pct=50.0,
    )
    cash = PositionBreakdown(
        name="USD", category="cash", value_usd=100.0, value_twd=3200.0,
        portfolio_pct=20.0, quantity=100, unit_price=None, price_currency="USD",
        average_cost=None, total_cost_usd=100.0, total_cost_twd=3200.0,
        unrealized_pl_usd=0.0, unrealized_pl_twd=0.0, roi_pct=0.0,
    )
    return PortfolioResult(totals=totals, positions=[pos, cash])


def test_report_contains_totals_and_holding_opinion():
    card = OpinionCard("NVDA", ADD, "high", "量能轉強", ("volume_zscore",), DISCLAIMER, "deterministic")
    report = build_report(_result(), {"NVDA": card}, as_of="2026-06-19", daily_return_pct=1.5)

    assert report.as_of == "2026-06-19"
    assert "NVDA" in report.text
    assert "加碼觀察" in report.text  # opinion label rendered
    assert "+1.50%" in report.text  # daily return
    assert DISCLAIMER in report.text

    assert report.summary["total_usd"] == 1600.0  # 1500 stock + 100 cash
    assert len(report.summary["holdings"]) == 1  # cash excluded from holdings
    assert report.summary["holdings"][0]["opinion_label"] == "加碼觀察"


def test_report_handles_missing_advice_card():
    report = build_report(_result(), {}, as_of="2026-06-19")
    assert report.summary["holdings"][0]["opinion_label"] == "—"
    assert DISCLAIMER in report.text
