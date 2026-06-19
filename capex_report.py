#!/usr/bin/env python3.13
"""CLI entry point to refresh the AI capex monitoring dashboard.

Pulls quarterly capex for the hyperscaler / chip-maker watch-list via yfinance,
derives the rate-of-change signal, prints a table, and rewrites the auto section
of docs/capex-monitor.md.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path
from typing import List

try:  # Optional rich-based rendering for nicer terminal output
    from rich import box
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console: Console | None = Console()
except ImportError:  # pragma: no cover - fallback to plain text output
    console = None

from app.infrastructure.capex_monitor import CapexMonitor, CapexSignal
from app.services.capex_service import LIGHT_EMOJI, TREND_LABEL, CapexService

_LIGHT_STYLE = {"green": "green", "yellow": "yellow", "red": "red", "unknown": "dim"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the AI capex monitor dashboard.")
    parser.add_argument(
        "--doc",
        type=Path,
        default=Path("docs/capex-monitor.md"),
        help="Markdown dashboard to update (default: docs/capex-monitor.md)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        help="Comma-separated tickers to override the default watch-list.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print the table without rewriting the markdown file.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (repeat for more detail).",
    )
    return parser.parse_args()


def configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(
        level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )


def _fmt_b(value: float | None) -> str:
    return "—" if value is None else f"{value / 1e9:.1f}"


def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1f}%"


def print_signals(signals: List[CapexSignal]) -> None:
    if console:
        table = Table(title="AI Capex 監控（實際季 capex 拐點）", box=box.SIMPLE_HEAVY)
        for col, justify in (
            ("代號", "left"),
            ("最新季", "left"),
            ("capex(B)", "right"),
            ("幣別", "left"),
            ("YoY", "right"),
            ("QoQ", "right"),
            ("趨勢", "left"),
            ("燈號", "center"),
            ("下次財報", "left"),
        ):
            table.add_column(col, justify=justify)
        for s in signals:
            style = _LIGHT_STYLE.get(s.light, "")
            table.add_row(
                s.symbol,
                s.latest_period or "—",
                _fmt_b(s.latest_capex),
                s.currency or "—",
                _fmt_pct(s.yoy_growth_pct),
                _fmt_pct(s.qoq_growth_pct),
                TREND_LABEL.get(s.trend, s.trend),
                Text(LIGHT_EMOJI.get(s.light, "⬜"), style=style),
                s.next_earnings or "—",
            )
        console.print(table)
    else:
        for s in signals:
            print(
                f"{s.symbol:<6} {s.latest_period or '—':<11} "
                f"capex={_fmt_b(s.latest_capex):>6}B  YoY={_fmt_pct(s.yoy_growth_pct):>8}  "
                f"{LIGHT_EMOJI.get(s.light, '⬜')} {s.trend}  next={s.next_earnings or '—'}"
            )


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    symbols = (
        [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        if args.symbols
        else None
    )

    service = CapexService(CapexMonitor())
    signals = service.collect(symbols)
    print_signals(signals)

    if args.no_write:
        print("--no-write: docs not updated.")
        return

    try:
        service.update_markdown_file(args.doc, signals, as_of=date.today().isoformat())
        print(f"Updated {args.doc}")
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"Failed to update {args.doc}: {exc}") from exc


if __name__ == "__main__":
    main()
