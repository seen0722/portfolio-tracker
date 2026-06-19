"""Advice value objects — the read-only opinion the narrator produces.

An OpinionCard is decision-SUPPORT, never an order. There is deliberately no
order-placement field or seam anywhere in the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

ADD, TRIM, HOLD = "add", "trim", "hold"

OPINION_LABELS = {ADD: "加碼觀察", TRIM: "減碼觀察", HOLD: "持有"}

# The disclaimer is injected server-side by AdviceService and never trusted
# from a model — see honest-by-construction design.
DISCLAIMER = "本內容由量化訊號自動彙整，僅供教育參考，不構成投資建議。"


@dataclass(frozen=True)
class OpinionCard:
    """A narrated, read-only opinion grounded in an EvidenceBundle."""

    symbol: str
    opinion: str  # ADD / TRIM / HOLD
    confidence: str  # low / medium / high
    rationale: str
    cited_signals: Tuple[str, ...]
    disclaimer: str = ""
    source: str = "deterministic"  # or "llm"

    @property
    def opinion_label(self) -> str:
        return OPINION_LABELS.get(self.opinion, self.opinion)

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "opinion": self.opinion,
            "opinion_label": self.opinion_label,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "cited_signals": list(self.cited_signals),
            "disclaimer": self.disclaimer,
            "source": self.source,
        }
