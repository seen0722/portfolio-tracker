"""Optional LLM-backed narrator (BYO key). Used only when LLM_API_KEY is set;
otherwise the app uses the DeterministicNarrator.

`build_prompt` and `parse_opinion` are pure and unit-tested; the HTTP call is the
single network seam. The prompt constrains the model to the supplied signals, and
the AdviceService guardrail enforces that constraint regardless of model behaviour.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from app.domain.advice import ADD, HOLD, TRIM, OpinionCard
from app.domain.signals import EvidenceBundle

logger = logging.getLogger(__name__)

_VALID_OPINIONS = {ADD, TRIM, HOLD}
_VALID_CONFIDENCE = {"low", "medium", "high"}
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def build_prompt(bundle: EvidenceBundle, context: Dict[str, Any]) -> str:
    payload = {
        "holding": bundle.symbol,
        "position_context": context or {},
        "signals": bundle.to_dict()["signals"],
    }
    return (
        "你是一位嚴謹的股票分析助理。以下提供某持倉的『確定性量化訊號』與部位資訊。\n"
        "規則：\n"
        "1. 只能依據下方 signals 判斷，不得引用任何未列出的資訊或自行假設數據。\n"
        "2. 你的角色是『解說整理』這些訊號，不是預測股價。\n"
        "3. 嚴格只輸出一個 JSON 物件，格式：\n"
        '{"opinion":"add|trim|hold","confidence":"low|medium|high",'
        '"rationale":"繁體中文 2-4 句，逐一對應訊號","cited_signals":["實際用到的 signal_id"]}\n\n'
        f"資料：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n只輸出 JSON，不要其他文字。"
    )


def parse_opinion(text: str) -> Dict[str, Any]:
    """Extract the first JSON object from the model text; {} on failure."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except (ValueError, TypeError):
        return {}


class LlmNarratorClient:
    """Anthropic Messages API narrator (provider-agnostic seam at _call)."""

    source = "llm"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        provider: str = "anthropic",
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self.timeout = timeout

    def validate(self) -> None:
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY is empty")

    def narrate(self, bundle: EvidenceBundle, context: Dict[str, Any]) -> OpinionCard:
        text = self._call(build_prompt(bundle, context))
        data = parse_opinion(text)

        opinion = data.get("opinion", HOLD)
        if opinion not in _VALID_OPINIONS:
            opinion = HOLD
        confidence = data.get("confidence", "low")
        if confidence not in _VALID_CONFIDENCE:
            confidence = "low"
        rationale = str(data.get("rationale", "")).strip() or "（無法解析模型輸出，退回保守判讀）"
        cited = tuple(str(c) for c in data.get("cited_signals", []) or [])

        return OpinionCard(
            symbol=bundle.symbol,
            opinion=opinion,
            confidence=confidence,
            rationale=rationale,
            cited_signals=cited,
            source=self.source,
        )

    def _call(self, prompt: str) -> str:
        import requests

        resp = requests.post(
            _ANTHROPIC_URL,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return "".join(block.get("text", "") for block in data.get("content", []))
