"""Compose the daily report from valuation + analytics + advice.

`build_report` is a pure transform (no network/IO), so it carries the test weight.
It produces both a plain-text body (for Telegram/email) and a structured summary
(for the HTML preview / JSON).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.domain.advice import DISCLAIMER, OpinionCard
from app.domain.models import PortfolioResult


@dataclass(frozen=True)
class ReportContent:
    as_of: str
    title: str
    text: str
    summary: Dict


def build_report(
    result: PortfolioResult,
    advice_cards: Dict[str, OpinionCard],
    as_of: str,
    daily_return_pct: float = 0.0,
    analysis: Optional[object] = None,
) -> ReportContent:
    totals = result.totals
    title = f"投資組合日報 {as_of}"

    lines: List[str] = [
        f"📊 {title}",
        f"總值 ${totals.usd:,.0f}（NT${totals.twd:,.0f}）",
        f"未實現損益 ${totals.unrealized_pl_usd:,.0f}（{totals.roi_pct:+.1f}%）",
        f"當日 {daily_return_pct:+.2f}%",
        "",
        "持倉觀察：",
    ]

    holdings: List[Dict] = []
    for pos in result.positions:
        if pos.category != "stock":
            continue
        card = advice_cards.get(pos.name)
        opinion = card.opinion_label if card else "—"
        lines.append(
            f"• {pos.name}: {opinion}｜報酬 {pos.roi_pct:+.1f}%｜市值 ${pos.value_usd:,.0f}"
        )
        holdings.append(
            {
                "symbol": pos.name,
                "opinion": card.opinion if card else "",
                "opinion_label": opinion,
                "confidence": card.confidence if card else "",
                "rationale": card.rationale if card else "",
                "roi_pct": round(pos.roi_pct, 2),
                "value_usd": round(pos.value_usd, 2),
                "unrealized_pl_usd": round(pos.unrealized_pl_usd, 2),
            }
        )

    disclaimer = DISCLAIMER
    lines += ["", disclaimer]
    text = "\n".join(lines)

    summary = {
        "as_of": as_of,
        "total_usd": round(totals.usd, 2),
        "total_twd": round(totals.twd, 2),
        "unrealized_pl_usd": round(totals.unrealized_pl_usd, 2),
        "roi_pct": round(totals.roi_pct, 2),
        "daily_return_pct": round(daily_return_pct, 2),
        "holdings": holdings,
        "disclaimer": disclaimer,
    }
    return ReportContent(as_of=as_of, title=title, text=text, summary=summary)
