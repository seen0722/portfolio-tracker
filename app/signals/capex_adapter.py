"""Adapt the existing CapexMonitor into the unified Signal contract, so capex
participates in the EvidenceBundle alongside volume (and future signals).
"""

from __future__ import annotations

from datetime import date

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
from app.infrastructure.capex_monitor import CapexMonitor, CapexSignal

SIGNAL_ID = "capex_roc"
VERSION = 1

_DIRECTION = {
    "accelerating": BULLISH,
    "decelerating": BEARISH,
    "stable": NEUTRAL,
    "unknown": NEUTRAL,
}
_SCORE_BY_LIGHT = {GREEN: 0.3, YELLOW: -0.3, RED: -0.7, UNKNOWN: 0.0}


def capex_to_signal(cs: CapexSignal) -> SignalOutput:
    """Pure mapping CapexSignal -> SignalOutput."""
    light = cs.light if cs.light in (GREEN, YELLOW, RED) else UNKNOWN
    direction = _DIRECTION.get(cs.trend, NEUTRAL)
    magnitude = float(cs.yoy_growth_pct) if cs.yoy_growth_pct is not None else 0.0
    score = _SCORE_BY_LIGHT.get(light, 0.0)
    as_of = cs.latest_period or date.today().isoformat()
    return SignalOutput(
        symbol=cs.symbol,
        signal_id=SIGNAL_ID,
        version=VERSION,
        score=round(score, 3),
        light=light,
        direction=direction,
        magnitude=magnitude,
        evidence=cs.note or "capex 訊號",
        as_of=as_of,
    )


class CapexSignalAdapter:
    """Wraps CapexMonitor behind the Signal protocol."""

    signal_id = SIGNAL_ID
    version = VERSION

    def __init__(self, monitor: CapexMonitor) -> None:
        self.monitor = monitor

    def for_symbol(self, symbol: str) -> SignalOutput:
        return capex_to_signal(self.monitor.get_signal(symbol))
