#!/usr/bin/env python3.13
"""CLI entry point to value the portfolio and persist history."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from history_repository import HistoryRepository
from portfolio_tracker import PortfolioCalculator, PortfolioResult
from price_fetcher import PriceFetchError, PriceFetcher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update the portfolio history with the latest valuations."
    )
    parser.add_argument(
        "--portfolio",
        type=Path,
        default=Path("portfolio.json"),
        help="Path to the portfolio configuration file (default: portfolio.json)",
    )
    parser.add_argument(
        "--overrides",
        type=Path,
        default=Path("price_overrides.json"),
        help="Path to local price overrides (default: price_overrides.json)",
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=Path("history.csv"),
        help="Path to the history CSV file (default: history.csv)",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Override the date for the history entry (format: YYYY-MM-DD)",
    )
    parser.add_argument(
        "--overrides-only",
        action="store_true",
        help="Disable online price sources and rely solely on local overrides.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate and display totals without updating history.csv.",
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
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def load_portfolio(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Portfolio file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Portfolio file must contain a JSON object.")
    data.setdefault("stocks", [])
    data.setdefault("cash", [])
    return data


def resolve_date(date_override: str | None) -> str:
    if not date_override:
        return date.today().isoformat()
    try:
        parsed = datetime.strptime(date_override, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"Invalid date format '{date_override}'. Use YYYY-MM-DD.") from exc
    return parsed.isoformat()


def print_summary(
    record_date: str,
    history_df: pd.DataFrame,
    fetcher: PriceFetcher,
    result: PortfolioResult,
) -> None:
    latest_row = history_df[history_df["date"] == record_date].iloc[-1]
    print(f"Portfolio value on {record_date}")
    print(f"  Total USD: ${latest_row['total_usd']:.2f}")
    print(f"  Total TWD: NT${latest_row['total_twd']:.2f}")
    print(f"  Daily return: {latest_row['daily_return_pct']:.2f}%")
    print(f"[INFO] {fetcher.describe_sources()}")
    print_breakdown(result)


def simulate_history(
    repository: HistoryRepository,
    record_date: str,
    result: PortfolioResult,
) -> pd.DataFrame:
    history_df = repository.load()
    history_df = history_df[history_df["date"] != record_date]
    summary_df = history_df.copy()
    summary_df = pd.concat(
        [
            summary_df,
            pd.DataFrame(
                [
                    {
                        "date": record_date,
                        "total_usd": round(result.totals.usd, 2),
                        "total_twd": round(result.totals.twd, 2),
                        "daily_return_pct": 0.0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    summary_df["date"] = pd.to_datetime(summary_df["date"])
    summary_df.sort_values("date", inplace=True)
    summary_df["daily_return_pct"] = (
        summary_df["total_usd"].pct_change().fillna(0.0) * 100.0
    )
    summary_df["date"] = summary_df["date"].dt.strftime("%Y-%m-%d")
    return summary_df


def print_breakdown(result: PortfolioResult) -> None:
    if not result.positions:
        return
    print("\n明細（USD/TWD 已換算）：")
    header = (
        f"{'類型':<8}{'標的/貨幣':<15}{'數量':>10}{'單價':>12}{'幣別':>8}"
        f"{'價值(USD)':>14}{'價值(TWD)':>14}{'佔比%':>10}"
    )
    print(header)
    print("-" * len(header))
    for pos in result.positions:
        quantity = f"{pos.quantity:.4f}" if pos.quantity is not None else "-"
        if pos.category == "cash":
            unit_price = "-"
        else:
            unit_price = f"{pos.unit_price:.4f}" if pos.unit_price is not None else "-"
        line = (
            f"{pos.category:<8}"
            f"{pos.name:<15}"
            f"{quantity:>10}"
            f"{unit_price:>12}"
            f"{(pos.price_currency or '-'):>8}"
            f"{pos.value_usd:>14.2f}"
            f"{pos.value_twd:>14.2f}"
            f"{pos.portfolio_pct:>10.2f}"
        )
        print(line)
    print()


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    record_date = resolve_date(args.date)
    fetcher = PriceFetcher(
        overrides_path=args.overrides,
        allow_online=not args.overrides_only,
    )
    calculator = PortfolioCalculator(fetcher)
    repository = HistoryRepository(args.history)

    try:
        portfolio = load_portfolio(args.portfolio)
    except Exception as exc:
        raise SystemExit(f"Failed to load portfolio file: {exc}") from exc

    try:
        result = calculator.calculate(portfolio)
    except PriceFetchError as exc:
        raise SystemExit(f"Failed to calculate portfolio totals: {exc}") from exc

    if args.dry_run:
        print("Dry run - history.csv not updated.")
        history_df = simulate_history(repository, record_date, result)
        print_summary(record_date, history_df, fetcher, result)
        return

    history_df = repository.upsert(record_date, result.totals.usd, result.totals.twd)
    print_summary(record_date, history_df, fetcher, result)


if __name__ == "__main__":
    main()
