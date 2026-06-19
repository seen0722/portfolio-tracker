"""Market regime engine — pure classifiers + aggregation over macro factors.

`build_indicator` and `compute_regime` are network-free and deterministic, so
they carry the unit-test weight (mirroring compute_capex_signal). The provider
supplies raw (value, reference) pairs; this turns them into lights/stances and a
composite Risk-On / Neutral / Risk-Off read for a growth-tilted book.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from app.domain.macro import (
    GREEN,
    HEADWIND,
    MacroIndicator,
    MarketRegime,
    NEUTRAL,
    RED,
    RISK_NEUTRAL,
    RISK_OFF,
    RISK_ON,
    TAILWIND,
    UNKNOWN,
    YELLOW,
)

# Factor specs. "bad_when" = the move direction that hurts a growth/tech book.
# "levels" (g, y): level-based light where higher is worse (VIX, credit spread).
# "inverted_level": curve-style where < 0 (inverted) is the warning.
SPECS: Dict[str, Dict] = {
    "VIX": {"label": "VIX 波動率", "unit": "", "source": "yfinance", "bad_when": "up", "weight": 1.2, "levels": (18.0, 25.0)},
    "HYOAS": {"label": "高收益信用利差", "unit": "%", "source": "FRED", "bad_when": "up", "weight": 1.2, "levels": (3.5, 5.0)},
    "T10Y2Y": {"label": "2s10s 殖利率曲線", "unit": "%", "source": "FRED", "bad_when": "down", "weight": 1.0, "inverted_level": True},
    "REAL10Y": {"label": "10Y 實質殖利率", "unit": "%", "source": "FRED", "bad_when": "up", "weight": 1.0},
    "US10Y": {"label": "10Y 名目殖利率", "unit": "%", "source": "yfinance", "bad_when": "up", "weight": 0.8},
    "DXY": {"label": "美元指數 DXY", "unit": "", "source": "yfinance", "bad_when": "up", "weight": 0.8},
    "SOX": {"label": "費城半導體 SOX", "unit": "", "source": "yfinance", "bad_when": "down", "weight": 0.8},
    "GOLD": {"label": "黃金", "unit": "$", "source": "yfinance", "bad_when": "up", "weight": 0.5},
    "WTI": {"label": "WTI 原油", "unit": "$", "source": "yfinance", "bad_when": "up", "weight": 0.5},
}

_FLAT_PCT = 0.2  # |change%| below this is treated as flat
_STANCE_FROM_LIGHT = {GREEN: TAILWIND, YELLOW: NEUTRAL, RED: HEADWIND}
_STANCE_SIGN = {TAILWIND: 1.0, HEADWIND: -1.0, NEUTRAL: 0.0}


def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 2)


def build_indicator(key: str, value: Optional[float], ref: Optional[float], as_of: str) -> MacroIndicator:
    """Pure: raw (value, reference) -> a classified MacroIndicator."""
    spec = SPECS[key]
    label, unit, source = spec["label"], spec["unit"], spec["source"]

    if value is None:
        return MacroIndicator(key, label, None, None, None, unit, UNKNOWN, NEUTRAL, "flat", as_of, source, "資料不足")

    change = (value - ref) if ref is not None else None
    change_pct = (change / ref * 100.0) if (ref not in (None, 0)) else None
    trend = "flat"
    if change is not None:
        trend = "up" if change > 1e-9 else ("down" if change < -1e-9 else "flat")

    if "levels" in spec:  # higher = worse (VIX, credit spread)
        green_max, yellow_max = spec["levels"]
        light = GREEN if value < green_max else (YELLOW if value < yellow_max else RED)
        stance = _STANCE_FROM_LIGHT[light]
    elif spec.get("inverted_level"):  # curve: < 0 inverted
        light = RED if value < 0 else (YELLOW if value < 0.2 else GREEN)
        stance = _STANCE_FROM_LIGHT[light]
    else:  # trend-based: light from adverse-move magnitude
        bad_when = spec["bad_when"]
        flat = change_pct is None or abs(change_pct) < _FLAT_PCT
        adverse = change is not None and ((change > 0 and bad_when == "up") or (change < 0 and bad_when == "down"))
        stance = NEUTRAL if flat else (HEADWIND if adverse else TAILWIND)
        mag = abs(change_pct) if change_pct is not None else 0.0
        if stance == HEADWIND and mag >= 4:
            light = RED
        elif stance == HEADWIND and mag >= 2:
            light = YELLOW
        else:
            light = GREEN

    return MacroIndicator(
        key=key, label=label, value=_round(value), change=_round(change), change_pct=_round(change_pct),
        unit=unit, light=light, stance=stance, trend=trend, as_of=as_of, source=source,
        note=_note(stance, trend),
    )


def _note(stance: str, trend: str) -> str:
    arrow = {"up": "↑", "down": "↓", "flat": "→"}.get(trend, "")
    word = {TAILWIND: "順風", HEADWIND: "逆風", NEUTRAL: "中性"}.get(stance, "")
    return f"{arrow} {word}".strip()


def compute_regime(indicators: Sequence[MacroIndicator], as_of: str) -> MarketRegime:
    """Aggregate stances (weighted) into a composite risk regime."""
    known = [i for i in indicators if i.light != UNKNOWN and i.key in SPECS]
    if not known:
        return MarketRegime(RISK_NEUTRAL, 0.0, "中性 Neutral", "市場數據不足", as_of, tuple(indicators))

    numerator = sum(SPECS[i.key]["weight"] * _STANCE_SIGN[i.stance] for i in known)
    denominator = sum(SPECS[i.key]["weight"] for i in known)
    score = numerator / denominator if denominator else 0.0

    if score >= 0.2:
        state, label = RISK_ON, "風險偏好 Risk-On"
    elif score <= -0.2:
        state, label = RISK_OFF, "風險趨避 Risk-Off"
    else:
        state, label = RISK_NEUTRAL, "中性 Neutral"

    headwinds: List[str] = [i.label for i in known if i.stance == HEADWIND]
    tailwinds: List[str] = [i.label for i in known if i.stance == TAILWIND]
    summary = f"逆風 {len(headwinds)} ／ 順風 {len(tailwinds)}"
    if headwinds:
        summary += "；主要逆風：" + "、".join(headwinds[:3])

    return MarketRegime(state, round(score, 3), label, summary, as_of, tuple(indicators))
