#!/usr/bin/env python3.13
"""Minimal Flask dashboard to visualize the portfolio on Render."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

from flask import Flask, abort, redirect, render_template, request, url_for
import pandas as pd

from history_repository import HistoryRepository
from portfolio_tracker import PortfolioCalculator
from price_fetcher import PriceFetchError, PriceFetcher
from main import load_portfolio, save_portfolio, simulate_history


PORTFOLIO_FILE = Path(os.environ.get("PORTFOLIO_FILE", "portfolio.json"))
PRICE_OVERRIDES_FILE = Path(os.environ.get("PRICE_OVERRIDES_FILE", "price_overrides.json"))
HISTORY_FILE = Path(os.environ.get("HISTORY_FILE", "history.csv"))
OVERRIDES_ONLY = os.environ.get("OVERRIDES_ONLY", "false").lower() == "true"
MAX_HISTORY_POINTS = int(os.environ.get("MAX_HISTORY_POINTS", "90"))

app = Flask(__name__)


def _resolve_record_date(requested_date: str | None, history_df: pd.DataFrame) -> str:
    if requested_date:
        return requested_date
    if not history_df.empty:
        return history_df.sort_values("date").iloc[-1]["date"]
    return date.today().isoformat()


def _chart_payload(history_df: pd.DataFrame) -> Tuple[List[str], List[float], List[float]]:
    limited = history_df.tail(MAX_HISTORY_POINTS)
    labels = limited["date"].tolist()
    totals = [round(value, 2) for value in limited["total_usd"].tolist()]
    returns = [round(value, 2) for value in limited["daily_return_pct"].tolist()]
    return labels, totals, returns


def _prepare_dashboard(requested_date: str | None) -> Dict[str, object]:
    fetcher = PriceFetcher(
        overrides_path=PRICE_OVERRIDES_FILE,
        allow_online=not OVERRIDES_ONLY,
    )
    calculator = PortfolioCalculator(fetcher)
    repository = HistoryRepository(HISTORY_FILE)
    history_df = repository.load()
    record_date = _resolve_record_date(requested_date, history_df)

    try:
        portfolio = load_portfolio(PORTFOLIO_FILE)
    except (FileNotFoundError, ValueError) as exc:
        abort(404, f"Failed to load portfolio file: {exc}")

    try:
        result = calculator.calculate(portfolio)
    except PriceFetchError as exc:
        abort(503, f"Failed to calculate portfolio totals: {exc}")

    if history_df.empty or record_date not in history_df["date"].values:
        history_df = simulate_history(repository, record_date, result)

    if history_df.empty:
        abort(500, "History dataset is empty; run the CLI once to seed history.csv.")

    summary_row = history_df[history_df["date"] == record_date].iloc[-1]
    chart_labels, chart_totals, chart_returns = _chart_payload(history_df)

    # Prepare allocation data for Pie Chart
    allocation_labels = [pos.name for pos in result.positions if pos.portfolio_pct > 0]
    allocation_data = [round(pos.portfolio_pct, 2) for pos in result.positions if pos.portfolio_pct > 0]

    return {
        "result": result,
        "record_date": record_date,
        "summary": {
            "total_usd": summary_row["total_usd"],
            "total_twd": summary_row["total_twd"],
            "daily_return_pct": summary_row["daily_return_pct"],
        },
        "history_labels": chart_labels,
        "history_totals": chart_totals,
        "history_returns": chart_returns,
        "allocation_labels": allocation_labels,
        "allocation_data": allocation_data,
        "price_sources": fetcher.describe_sources(),
    }


@app.get("/")
def dashboard() -> str:
    context = _prepare_dashboard(request.args.get("date"))
    return render_template("dashboard.html", **context)


@app.route("/edit", methods=["GET", "POST"])
def edit_portfolio() -> str:
    if request.method == "POST":
        # Reconstruct portfolio from form data
        new_portfolio: Dict[str, List[Dict[str, object]]] = {"stocks": [], "cash": []}
        
        # Process stocks
        symbols = request.form.getlist("stock_symbol[]")
        shares = request.form.getlist("stock_shares[]")
        costs = request.form.getlist("stock_cost[]")
        
        for s, sh, c in zip(symbols, shares, costs):
            if s and sh:  # Basic validation
                new_portfolio["stocks"].append({
                    "symbol": s.strip().upper(),
                    "shares": float(sh),
                    "average_cost": float(c) if c else 0.0
                })

        # Process cash
        currencies = request.form.getlist("cash_currency[]")
        amounts = request.form.getlist("cash_amount[]")
        
        for cur, amt in zip(currencies, amounts):
            if cur and amt:
                new_portfolio["cash"].append({
                    "currency": cur.strip().upper(),
                    "amount": float(amt)
                })

        try:
            save_portfolio(PORTFOLIO_FILE, new_portfolio)
            return redirect(url_for("dashboard", date=date.today().isoformat()))
        except Exception as e:
            abort(500, f"Failed to save portfolio: {e}")
            
    # GET request
    try:
        portfolio = load_portfolio(PORTFOLIO_FILE)
    except (FileNotFoundError, ValueError):
        portfolio = {"stocks": [], "cash": []}
        
    return render_template("edit_portfolio.html", portfolio=portfolio)



@app.get("/healthz")
def healthcheck() -> str:
    return "ok", 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
