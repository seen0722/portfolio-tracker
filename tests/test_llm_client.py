"""Unit tests for the pure parts of the LLM narrator (prompt + parse)."""

from app.domain.signals import BULLISH, EvidenceBundle, GREEN, SignalOutput
from app.infrastructure.llm_client import build_prompt, parse_opinion


def _bundle():
    sig = SignalOutput("NVDA", "volume_zscore", 1, 0.5, GREEN, BULLISH, 1.8, "量能 1.4×", "2026-06-19")
    return EvidenceBundle("NVDA", "2026-06-19", (sig,))


def test_prompt_includes_signal_and_constraints():
    prompt = build_prompt(_bundle(), {"roi_pct": 12.3})
    assert "volume_zscore" in prompt
    assert "JSON" in prompt
    assert "不得引用" in prompt  # constrained to provided signals


def test_parse_extracts_json_object():
    text = 'Here is my answer:\n{"opinion":"add","confidence":"high","rationale":"r","cited_signals":["volume_zscore"]}\nThanks'
    data = parse_opinion(text)
    assert data["opinion"] == "add"
    assert data["cited_signals"] == ["volume_zscore"]


def test_parse_returns_empty_on_garbage():
    assert parse_opinion("no json here") == {}
    assert parse_opinion("") == {}
