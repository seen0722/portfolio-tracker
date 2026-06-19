"""Unit tests for the deterministic signal layer."""

import pytest

from app.domain.signals import (
    BEARISH,
    BULLISH,
    EvidenceBundle,
    GREEN,
    NEUTRAL,
    RED,
    SignalOutput,
    UNKNOWN,
    YELLOW,
)
from app.signals.capex_adapter import capex_to_signal
from app.signals.volume import compute_volume_signal
from app.infrastructure.capex_monitor import CapexSignal


def test_normal_volume_is_green_and_neutral():
    sig = compute_volume_signal("NVDA", [100] * 21, as_of="2026-06-19")
    assert sig.light == GREEN
    assert sig.direction == NEUTRAL
    assert sig.signal_id == "volume_zscore"
    assert sig.version == 1


def test_volume_spike_flags_yellow_or_red():
    volumes = [100] * 20 + [400]  # huge spike vs flat base
    sig = compute_volume_signal("NVDA", volumes, as_of="2026-06-19")
    assert sig.light in (YELLOW, RED)
    assert sig.magnitude > 2  # high z-score


def test_volume_spike_with_up_price_is_bullish():
    volumes = [100] * 20 + [400]
    sig = compute_volume_signal("NVDA", volumes, as_of="2026-06-19", price_change_pct=5.0)
    assert sig.direction == BULLISH
    assert sig.score > 0


def test_volume_spike_with_down_price_is_bearish():
    volumes = [100] * 20 + [400]
    sig = compute_volume_signal("NVDA", volumes, as_of="2026-06-19", price_change_pct=-5.0)
    assert sig.direction == BEARISH
    assert sig.score < 0


def test_insufficient_volume_is_unknown():
    sig = compute_volume_signal("NVDA", [100, 100], as_of="2026-06-19")
    assert sig.light == UNKNOWN


def test_capex_decelerating_red_maps_to_bearish():
    cs = CapexSignal(
        symbol="TSM", latest_period="2026-03-31", latest_capex=1e9,
        yoy_growth_pct=-5.0, qoq_growth_pct=None, yoy_prev_growth_pct=None,
        trend="decelerating", light="red", next_earnings=None, note="capex 連兩季減速",
    )
    sig = capex_to_signal(cs)
    assert sig.signal_id == "capex_roc"
    assert sig.direction == BEARISH
    assert sig.light == RED
    assert sig.score < 0


def test_evidence_bundle_lookup_and_serialization():
    a = SignalOutput("NVDA", "volume_zscore", 1, 0.5, GREEN, BULLISH, 1.2, "x", "2026-06-19")
    b = SignalOutput("NVDA", "capex_roc", 1, -0.7, RED, BEARISH, -5.0, "y", "2026-03-31")
    bundle = EvidenceBundle("NVDA", "2026-06-19", (a, b))
    assert bundle.signal_ids() == frozenset({"volume_zscore", "capex_roc"})
    assert bundle.get("capex_roc") is b
    assert bundle.get("missing") is None
    d = bundle.to_dict()
    assert d["symbol"] == "NVDA"
    assert len(d["signals"]) == 2
