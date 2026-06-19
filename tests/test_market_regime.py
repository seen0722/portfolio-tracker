"""Unit tests for the pure market-regime engine."""

from app.domain.macro import (
    GREEN,
    HEADWIND,
    RED,
    RISK_OFF,
    RISK_ON,
    RISK_NEUTRAL,
    TAILWIND,
    UNKNOWN,
)
from app.services.market_regime import build_indicator, compute_regime


def test_low_vix_is_green_tailwind():
    ind = build_indicator("VIX", value=14.0, ref=15.0, as_of="2026-06-19")
    assert ind.light == GREEN
    assert ind.stance == TAILWIND


def test_high_vix_is_red_headwind():
    ind = build_indicator("VIX", value=30.0, ref=22.0, as_of="2026-06-19")
    assert ind.light == RED
    assert ind.stance == HEADWIND


def test_inverted_curve_is_red_headwind():
    ind = build_indicator("T10Y2Y", value=-0.3, ref=-0.1, as_of="2026-06-19")
    assert ind.light == RED
    assert ind.stance == HEADWIND


def test_rising_yield_is_headwind_for_growth():
    # 10Y up ~5% over the week -> adverse for a growth book
    ind = build_indicator("US10Y", value=4.62, ref=4.40, as_of="2026-06-19")
    assert ind.stance == HEADWIND
    assert ind.trend == "up"


def test_falling_yield_is_tailwind():
    ind = build_indicator("US10Y", value=4.18, ref=4.40, as_of="2026-06-19")
    assert ind.stance == TAILWIND


def test_unknown_value_is_unknown():
    ind = build_indicator("DXY", value=None, ref=None, as_of="2026-06-19")
    assert ind.light == UNKNOWN


def test_regime_risk_off_when_headwinds_dominate():
    inds = [
        build_indicator("VIX", 30.0, 20.0, "2026-06-19"),
        build_indicator("HYOAS", 5.5, 4.0, "2026-06-19"),
        build_indicator("US10Y", 4.7, 4.4, "2026-06-19"),
    ]
    regime = compute_regime(inds, "2026-06-19")
    assert regime.risk_state == RISK_OFF
    assert regime.score < 0


def test_regime_risk_on_when_tailwinds_dominate():
    inds = [
        build_indicator("VIX", 13.0, 15.0, "2026-06-19"),
        build_indicator("HYOAS", 3.0, 3.4, "2026-06-19"),
        build_indicator("US10Y", 4.1, 4.4, "2026-06-19"),
    ]
    regime = compute_regime(inds, "2026-06-19")
    assert regime.risk_state == RISK_ON
    assert regime.score > 0


def test_regime_neutral_when_no_data():
    inds = [build_indicator("DXY", None, None, "2026-06-19")]
    regime = compute_regime(inds, "2026-06-19")
    assert regime.risk_state == RISK_NEUTRAL
