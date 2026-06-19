"""Unit tests for the deterministic narrator and the AdviceService guardrail."""

from app.domain.advice import ADD, DISCLAIMER, HOLD, TRIM, OpinionCard
from app.domain.signals import (
    BEARISH,
    BULLISH,
    EvidenceBundle,
    GREEN,
    NEUTRAL,
    RED,
    SignalOutput,
    UNKNOWN,
)
from app.services.advice_service import AdviceService
from app.services.deterministic_narrator import DeterministicNarrator


def _sig(signal_id, score, light=GREEN, direction=NEUTRAL):
    return SignalOutput("NVDA", signal_id, 1, score, light, direction, 0.0, "evidence", "2026-06-19")


def _bundle(*signals):
    return EvidenceBundle("NVDA", "2026-06-19", tuple(signals))


def test_deterministic_bullish_signals_suggest_add():
    bundle = _bundle(_sig("volume_zscore", 0.5, GREEN, BULLISH), _sig("capex_roc", 0.3, GREEN, BULLISH))
    card = DeterministicNarrator().narrate(bundle, {})
    assert card.opinion == ADD
    assert card.confidence == "high"
    assert set(card.cited_signals) == {"volume_zscore", "capex_roc"}


def test_deterministic_bearish_signals_suggest_trim():
    bundle = _bundle(_sig("volume_zscore", -0.5, RED, BEARISH), _sig("capex_roc", -0.4, RED, BEARISH))
    card = DeterministicNarrator().narrate(bundle, {})
    assert card.opinion == TRIM


def test_deterministic_neutral_or_unknown_holds():
    bundle = _bundle(_sig("volume_zscore", 0.0, GREEN, NEUTRAL), _sig("capex_roc", 0.0, UNKNOWN, NEUTRAL))
    card = DeterministicNarrator().narrate(bundle, {})
    assert card.opinion == HOLD


class _PhantomNarrator:
    """Narrator that cites a signal not present in the bundle (to test guardrail)."""

    source = "llm"

    def narrate(self, bundle, context):
        return OpinionCard(
            symbol=bundle.symbol,
            opinion=ADD,
            confidence="high",
            rationale="references a made-up signal",
            cited_signals=("volume_zscore", "made_up_signal"),
            disclaimer="MODEL SAYS no disclaimer",
            source="llm",
        )


class _FixedOrchestrator:
    def __init__(self, bundle):
        self._bundle = bundle

    def bundle_for(self, symbol):
        return self._bundle

    def bundles_for(self, symbols):
        return {s: self._bundle for s in symbols}


def test_guardrail_drops_phantom_citations_and_injects_disclaimer():
    bundle = _bundle(_sig("volume_zscore", 0.5, GREEN, BULLISH))
    svc = AdviceService(_FixedOrchestrator(bundle), _PhantomNarrator())
    card = svc.advise("NVDA")
    # phantom citation removed, only the real signal remains
    assert card.cited_signals == ("volume_zscore",)
    # server-side disclaimer overrides whatever the model claimed
    assert card.disclaimer == DISCLAIMER
    assert "no disclaimer" not in card.disclaimer


def test_advise_many_returns_card_per_symbol():
    bundle = _bundle(_sig("volume_zscore", 0.1, GREEN, NEUTRAL))
    svc = AdviceService(_FixedOrchestrator(bundle), DeterministicNarrator())
    cards = svc.advise_many(["NVDA", "GOOG"])
    assert set(cards.keys()) == {"NVDA", "GOOG"}
    assert all(c.disclaimer == DISCLAIMER for c in cards.values())
