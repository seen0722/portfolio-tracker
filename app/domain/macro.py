"""Market-wide macro factors — a parallel to the per-holding signal layer.

Macro indicators describe the *regime* the whole book trades in (rates, the
dollar, volatility, credit, commodities). Like SignalOutput/EvidenceBundle they
are frozen value objects produced by a pure classifier; MarketRegime is the
market-level analogue of an EvidenceBundle and is used as background CONTEXT for
advice — never as a precise per-stock buy/sell trigger.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

GREEN, YELLOW, RED, UNKNOWN = "green", "yellow", "red", "unknown"
# Stance is framed for a growth/tech-tilted book (the user's holdings).
TAILWIND, HEADWIND, NEUTRAL = "tailwind", "headwind", "neutral"
RISK_ON, RISK_NEUTRAL, RISK_OFF = "risk_on", "neutral", "risk_off"


@dataclass(frozen=True)
class MacroIndicator:
    key: str
    label: str
    value: Optional[float]
    change: Optional[float]  # vs the reference point (≈1 week ago)
    change_pct: Optional[float]
    unit: str
    light: str  # green / yellow / red / unknown
    stance: str  # tailwind / headwind / neutral (for a growth book)
    trend: str  # up / down / flat
    as_of: str
    source: str
    note: str = ""

    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "change": self.change,
            "change_pct": self.change_pct,
            "unit": self.unit,
            "light": self.light,
            "stance": self.stance,
            "trend": self.trend,
            "as_of": self.as_of,
            "source": self.source,
            "note": self.note,
        }


@dataclass(frozen=True)
class MarketRegime:
    risk_state: str  # risk_on / neutral / risk_off
    score: float  # [-1, 1]; positive = supportive, negative = adverse
    label: str
    summary: str
    as_of: str
    indicators: Tuple[MacroIndicator, ...] = ()

    def to_dict(self) -> Dict:
        return {
            "risk_state": self.risk_state,
            "score": self.score,
            "label": self.label,
            "summary": self.summary,
            "as_of": self.as_of,
            "indicators": [i.to_dict() for i in self.indicators],
        }
