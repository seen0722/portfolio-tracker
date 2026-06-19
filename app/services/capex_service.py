"""Service that orchestrates the capex watch-list and renders the dashboard table."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.infrastructure.capex_monitor import (
    DEMAND_SIDE,
    SUPPLY_SIDE,
    CapexMonitor,
    CapexSignal,
)

logger = logging.getLogger(__name__)

LIGHT_EMOJI = {"green": "🟢", "yellow": "🟡", "red": "🔴", "unknown": "⬜"}
TREND_LABEL = {
    "accelerating": "加速 ↑",
    "decelerating": "減速 ↓",
    "stable": "持平 →",
    "unknown": "—",
}

# Section in docs/capex-monitor.md that gets overwritten on each run.
AUTO_START = "<!-- AUTO:capex:start -->"
AUTO_END = "<!-- AUTO:capex:end -->"


def _fmt_billions(value: Optional[float]) -> str:
    return "—" if value is None else f"{value / 1e9:.1f}"


def _fmt_pct(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:+.1f}%"


@dataclass
class CapexService:
    """Collects capex signals and turns them into the markdown dashboard table."""

    monitor: CapexMonitor

    def default_symbols(self) -> List[str]:
        return list(DEMAND_SIDE) + list(SUPPLY_SIDE)

    def collect(self, symbols: Optional[List[str]] = None) -> List[CapexSignal]:
        """Return signals in the requested order (defaults to the full watch-list)."""
        ordered = symbols if symbols is not None else self.default_symbols()
        signal_map = self.monitor.get_signals(ordered)
        return [signal_map[symbol] for symbol in ordered if symbol in signal_map]

    def render_markdown_table(self, signals: List[CapexSignal]) -> str:
        """Render signals as a markdown table (the auto-filled dashboard rows)."""
        header = (
            "| 代號 | 最新季 | 季 capex (B) | 幣別 | YoY | QoQ | 趨勢 | 燈號 | 下次財報 |\n"
            "|------|--------|-------------|------|-----|-----|------|------|----------|"
        )
        rows = [
            "| {symbol} | {period} | {capex} | {currency} | {yoy} | {qoq} | {trend} | {light} | {earnings} |".format(
                symbol=s.symbol,
                period=s.latest_period or "—",
                capex=_fmt_billions(s.latest_capex),
                currency=s.currency or "—",
                yoy=_fmt_pct(s.yoy_growth_pct),
                qoq=_fmt_pct(s.qoq_growth_pct),
                trend=TREND_LABEL.get(s.trend, s.trend),
                light=LIGHT_EMOJI.get(s.light, "⬜"),
                earnings=s.next_earnings or "—",
            )
            for s in signals
        ]
        return "\n".join([header, *rows])

    def update_markdown_file(
        self,
        path: Path,
        signals: List[CapexSignal],
        as_of: str = "",
    ) -> None:
        """Replace the AUTO section of the dashboard file with a fresh table."""
        text = path.read_text(encoding="utf-8")
        if AUTO_START not in text or AUTO_END not in text:
            raise ValueError(
                f"Auto markers not found in {path}; expected {AUTO_START} / {AUTO_END}"
            )

        prefix, rest = text.split(AUTO_START, 1)
        _, suffix = rest.split(AUTO_END, 1)

        stamp = f"_最後自動更新：{as_of}_\n\n" if as_of else ""
        block = f"{stamp}{self.render_markdown_table(signals)}"
        new_text = f"{prefix}{AUTO_START}\n{block}\n{AUTO_END}{suffix}"
        path.write_text(new_text, encoding="utf-8")
        logger.info("Updated capex auto section in %s", path)
