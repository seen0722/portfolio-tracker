"""Volume(量能) z-score signal — flags unusual trading activity vs a 20-day base.

`compute_volume_signal` is pure and network-free (carries the test weight);
`VolumeSignal._fetch` is the single yfinance seam, mirroring capex_monitor.
"""

from __future__ import annotations

import logging
import statistics
from datetime import date
from typing import List, Optional, Sequence, Tuple

import yfinance as yf

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

logger = logging.getLogger(__name__)

SIGNAL_ID = "volume_zscore"
VERSION = 1
LOOKBACK = 20
MIN_POINTS = 5


def compute_volume_signal(
    symbol: str,
    volumes: Sequence[float],
    as_of: str,
    price_change_pct: Optional[float] = None,
) -> SignalOutput:
    """Latest volume vs the mean/std of the prior LOOKBACK sessions -> a light.

    Volume is directionless on its own; when a price change is supplied, an
    unusual-volume day is read as confirming that move (bullish/bearish).
    """
    clean = [float(v) for v in volumes if v is not None and v > 0]
    if len(clean) < MIN_POINTS:
        return SignalOutput(symbol, SIGNAL_ID, VERSION, 0.0, UNKNOWN, NEUTRAL, 0.0, "量能資料不足", as_of)

    latest = clean[-1]
    prior = clean[-(LOOKBACK + 1):-1] if len(clean) > LOOKBACK else clean[:-1]
    mean = statistics.mean(prior)
    std = statistics.pstdev(prior) if len(prior) > 1 else 0.0
    ratio = latest / mean if mean else 0.0
    if std > 0:
        z = (latest - mean) / std
    else:
        # Flat base (zero variance): approximate intensity from the volume ratio
        # so a spike still registers instead of collapsing to z=0.
        z = (ratio - 1.0) * 4.0

    if abs(z) >= 3:
        light = RED
    elif abs(z) >= 2:
        light = YELLOW
    else:
        light = GREEN

    if price_change_pct is None or abs(z) < 1:
        direction = NEUTRAL
    elif price_change_pct > 0:
        direction = BULLISH
    else:
        direction = BEARISH

    magnitude = max(-1.0, min(1.0, z / 3.0))
    if direction == BULLISH:
        score = abs(magnitude)
    elif direction == BEARISH:
        score = -abs(magnitude)
    else:
        score = 0.0

    pc = f"，價格 {price_change_pct:+.1f}%" if price_change_pct is not None else ""
    evidence = f"成交量 {ratio:.1f}× 20日均量 (z={z:+.1f}){pc}"
    return SignalOutput(symbol, SIGNAL_ID, VERSION, round(score, 3), light, direction, round(z, 2), evidence, as_of)


class VolumeSignal:
    """yfinance-backed volume signal."""

    signal_id = SIGNAL_ID
    version = VERSION

    def __init__(self, allow_online: bool = True) -> None:
        self.allow_online = allow_online

    def for_symbol(self, symbol: str) -> SignalOutput:
        volumes, price_change, as_of = self._fetch(symbol)
        return compute_volume_signal(symbol, volumes, as_of, price_change)

    def _fetch(self, symbol: str) -> Tuple[List[float], Optional[float], str]:
        today = date.today().isoformat()
        if not self.allow_online:
            return [], None, today
        try:
            hist = yf.Ticker(symbol).history(period="2mo")
            if hist is None or hist.empty or "Volume" not in hist:
                return [], None, today
            volumes = [float(v) for v in hist["Volume"].dropna().tolist()]
            closes = [float(c) for c in hist["Close"].dropna().tolist()]
            price_change = (
                (closes[-1] - closes[-2]) / closes[-2] * 100.0
                if len(closes) >= 2 and closes[-2]
                else None
            )
            as_of = str(hist.index[-1])[:10]
            return volumes, price_change, as_of
        except Exception as exc:  # degrade gracefully, never crash the page
            logger.warning("Volume fetch failed for %s: %s", symbol, exc)
            return [], None, today
