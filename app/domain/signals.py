"""Signal value objects — the deterministic engine's output and the frozen
EvidenceBundle that is the ONLY thing the LLM layer is ever allowed to see.

Versioning every SignalOutput makes signals reproducible/auditable, and the
EvidenceBundle being frozen + the guardrail (AdviceService, Phase 7) is how
"decision-support, not oracle" is enforced by architecture, not by a disclaimer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# Shared light semantics: green = nothing notable, yellow = watch,
# red = strong/notable, unknown = insufficient data.
GREEN, YELLOW, RED, UNKNOWN = "green", "yellow", "red", "unknown"
BULLISH, BEARISH, NEUTRAL = "bullish", "bearish", "neutral"


@dataclass(frozen=True)
class SignalOutput:
    """One deterministic signal reading for one symbol."""

    symbol: str
    signal_id: str
    version: int
    score: float  # signed, normalized to [-1, 1]
    light: str
    direction: str
    magnitude: float  # raw magnitude (z-score, YoY %, ...)
    evidence: str
    as_of: str


@dataclass(frozen=True)
class EvidenceBundle:
    """Frozen, complete set of signals for one symbol — the LLM's sole input."""

    symbol: str
    as_of: str
    signals: Tuple[SignalOutput, ...] = ()

    def signal_ids(self) -> frozenset:
        return frozenset(s.signal_id for s in self.signals)

    def get(self, signal_id: str) -> Optional[SignalOutput]:
        return next((s for s in self.signals if s.signal_id == signal_id), None)

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of,
            "signals": [
                {
                    "signal_id": s.signal_id,
                    "version": s.version,
                    "score": s.score,
                    "light": s.light,
                    "direction": s.direction,
                    "magnitude": s.magnitude,
                    "evidence": s.evidence,
                    "as_of": s.as_of,
                }
                for s in self.signals
            ],
        }
