"""SignalOrchestrator — run the registered signals per symbol and assemble the
frozen EvidenceBundle. A signal that errors is skipped (graceful degradation),
never crashing the bundle.
"""

from __future__ import annotations

import concurrent.futures
import logging
from datetime import date
from typing import Dict, List, Sequence

from app.domain.protocols import Signal
from app.domain.signals import EvidenceBundle, SignalOutput

logger = logging.getLogger(__name__)


class SignalOrchestrator:
    """Runs a registry of signals to build EvidenceBundles."""

    def __init__(self, signals: Sequence[Signal]) -> None:
        self.signals: List[Signal] = list(signals)

    def bundle_for(self, symbol: str) -> EvidenceBundle:
        outputs: List[SignalOutput] = []
        for signal in self.signals:
            try:
                outputs.append(signal.for_symbol(symbol))
            except Exception as exc:  # one bad signal must not sink the bundle
                logger.warning("Signal %s failed for %s: %s", getattr(signal, "signal_id", "?"), symbol, exc)
        as_of = max((o.as_of for o in outputs), default=date.today().isoformat())
        return EvidenceBundle(symbol=symbol, as_of=as_of, signals=tuple(outputs))

    def bundles_for(self, symbols: Sequence[str]) -> Dict[str, EvidenceBundle]:
        results: Dict[str, EvidenceBundle] = {}
        if not symbols:
            return results
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_symbol = {
                executor.submit(self.bundle_for, symbol): symbol for symbol in symbols
            }
            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    results[symbol] = future.result()
                except Exception as exc:
                    logger.error("Bundle build failed for %s: %s", symbol, exc)
                    results[symbol] = EvidenceBundle(symbol=symbol, as_of=date.today().isoformat())
        return results
