"""Deterministic narrator — derives a read-only opinion purely from the signals.

No LLM, no network: net signal score -> add/trim/hold, with a transparent
rationale. This is the default narrator (works without an API key) and the
honest baseline the LLM narrator must not underperform on grounding.
"""

from __future__ import annotations

from typing import Any, Dict

from app.domain.advice import ADD, HOLD, TRIM, OpinionCard
from app.domain.signals import EvidenceBundle, UNKNOWN

_OPINION_THRESHOLD = 0.3
_LIGHT_LABEL = {"green": "🟢", "yellow": "🟡", "red": "🔴", "unknown": "⬜"}


class DeterministicNarrator:
    """Rule-based, fully reproducible opinion from an EvidenceBundle."""

    source = "deterministic"

    def narrate(self, bundle: EvidenceBundle, context: Dict[str, Any]) -> OpinionCard:
        scored = [s for s in bundle.signals if s.light != UNKNOWN]
        signal_net = sum(s.score for s in scored)

        # Market regime is background CONTEXT: it tilts the decision modestly,
        # it does not by itself decide. Confidence stays driven by the signals.
        market_score = context.get("market_score")
        decision_net = signal_net + (0.3 * float(market_score) if market_score is not None else 0.0)

        if decision_net >= _OPINION_THRESHOLD:
            opinion = ADD
        elif decision_net <= -_OPINION_THRESHOLD:
            opinion = TRIM
        else:
            opinion = HOLD

        if abs(signal_net) >= 0.6 and len(scored) >= 2:
            confidence = "high"
        elif scored:
            confidence = "medium"
        else:
            confidence = "low"

        lines = [
            f"{_LIGHT_LABEL.get(s.light, '⬜')} [{s.signal_id}] {s.evidence}"
            for s in bundle.signals
        ]
        market_label = context.get("market_label")
        if market_label:
            lines.append(f"🌐 市場環境:{market_label}")
        roi = context.get("roi_pct")
        if roi is not None:
            lines.append(f"目前未實現報酬率 {roi:+.1f}%")
        rationale = "\n".join(lines) if lines else "目前無可用訊號。"

        return OpinionCard(
            symbol=bundle.symbol,
            opinion=opinion,
            confidence=confidence,
            rationale=rationale,
            cited_signals=tuple(s.signal_id for s in bundle.signals),
            source=self.source,
        )
