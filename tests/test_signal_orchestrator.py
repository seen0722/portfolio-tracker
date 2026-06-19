"""Unit tests for the SignalOrchestrator (no network — fake signals)."""

from app.domain.signals import GREEN, NEUTRAL, SignalOutput
from app.services.signal_orchestrator import SignalOrchestrator


class _FakeSignal:
    def __init__(self, signal_id, score=0.0):
        self.signal_id = signal_id
        self.version = 1
        self._score = score

    def for_symbol(self, symbol):
        return SignalOutput(symbol, self.signal_id, 1, self._score, GREEN, NEUTRAL, 0.0, "ok", "2026-06-19")


class _BrokenSignal:
    signal_id = "broken"
    version = 1

    def for_symbol(self, symbol):
        raise RuntimeError("boom")


def test_bundle_collects_all_signals():
    orch = SignalOrchestrator([_FakeSignal("volume_zscore", 0.5), _FakeSignal("capex_roc", -0.7)])
    bundle = orch.bundle_for("NVDA")
    assert bundle.symbol == "NVDA"
    assert bundle.signal_ids() == frozenset({"volume_zscore", "capex_roc"})


def test_broken_signal_is_skipped_not_fatal():
    orch = SignalOrchestrator([_FakeSignal("volume_zscore"), _BrokenSignal()])
    bundle = orch.bundle_for("NVDA")
    assert bundle.signal_ids() == frozenset({"volume_zscore"})  # broken dropped


def test_bundles_for_multiple_symbols():
    orch = SignalOrchestrator([_FakeSignal("volume_zscore")])
    bundles = orch.bundles_for(["NVDA", "GOOG"])
    assert set(bundles.keys()) == {"NVDA", "GOOG"}
    assert all(b.get("volume_zscore") is not None for b in bundles.values())


def test_empty_symbols_returns_empty():
    orch = SignalOrchestrator([_FakeSignal("volume_zscore")])
    assert orch.bundles_for([]) == {}
