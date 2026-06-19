"""AdviceService — runs a narrator over an EvidenceBundle and enforces the
guardrail that makes "decision-support, not oracle" structural rather than a
disclaimer:

  1. The narrator's only input is the frozen bundle (it cannot invent signals).
  2. Any citation referencing a signal NOT in the bundle is dropped (and logged).
  3. The disclaimer is injected here, server-side, never trusted from the model.
  4. Read-only: there is no order-placement path anywhere.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Dict, List, Optional, Sequence

from app.domain.advice import DISCLAIMER, OpinionCard
from app.domain.protocols import LlmNarrator
from app.domain.signals import EvidenceBundle
from app.services.signal_orchestrator import SignalOrchestrator

logger = logging.getLogger(__name__)


class AdviceService:
    def __init__(self, orchestrator: SignalOrchestrator, narrator: LlmNarrator) -> None:
        self.orchestrator = orchestrator
        self.narrator = narrator

    def advise(self, symbol: str, context: Optional[Dict[str, Any]] = None) -> OpinionCard:
        bundle = self.orchestrator.bundle_for(symbol)
        return self.advise_bundle(bundle, context)

    def advise_bundle(
        self, bundle: EvidenceBundle, context: Optional[Dict[str, Any]] = None
    ) -> OpinionCard:
        raw = self.narrator.narrate(bundle, context or {})
        return self._apply_guardrail(raw, bundle)

    def advise_many(
        self,
        symbols: Sequence[str],
        contexts: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, OpinionCard]:
        bundles = self.orchestrator.bundles_for(symbols)
        contexts = contexts or {}
        return {
            symbol: self.advise_bundle(bundle, contexts.get(symbol))
            for symbol, bundle in bundles.items()
        }

    def _apply_guardrail(self, card: OpinionCard, bundle: EvidenceBundle) -> OpinionCard:
        valid_ids = bundle.signal_ids()
        cited_valid: List[str] = [c for c in card.cited_signals if c in valid_ids]
        phantom = set(card.cited_signals) - valid_ids
        if phantom:
            logger.warning(
                "Guardrail: narrator cited signals absent from bundle for %s: %s",
                bundle.symbol,
                phantom,
            )
        # Always inject the disclaimer server-side; drop phantom citations.
        return replace(card, cited_signals=tuple(cited_valid), disclaimer=DISCLAIMER)
