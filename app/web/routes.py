"""Web routes."""

from __future__ import annotations

from datetime import date
from typing import Dict, List

import pandas as pd

from flask import Blueprint, abort, redirect, render_template, request, url_for

from app.dependencies import (
    portfolio_service,
    history_repository,
    portfolio_repository,
    price_fetcher,
    analysis_service
)
from app.domain.models import Portfolio, Stock, Cash
from app.infrastructure.market_data import PriceFetchError

bp = Blueprint("main", __name__)

MAX_HISTORY_POINTS = 90

def _resolve_record_date(requested_date: str | None) -> str:
    if requested_date:
        return requested_date
    history_df = history_repository.load()
    if not history_df.empty:
        return history_df.sort_values("date").iloc[-1]["date"]
    return date.today().isoformat()

def _chart_payload(history_df):
    import math
    limited = history_df.tail(MAX_HISTORY_POINTS)
    labels = limited["date"].tolist()
    
    def clean_val(v):
        return None if pd.isna(v) or math.isnan(v) or math.isinf(v) else round(v, 2)

    totals = [clean_val(value) for value in limited["total_usd"].tolist()]
    returns = [clean_val(value) for value in limited["daily_return_pct"].tolist()]
    return labels, totals, returns

@bp.route("/")
def dashboard():
    requested_date = request.args.get("date")
    record_date = _resolve_record_date(requested_date)
    
    try:
        portfolio = portfolio_repository.load()
    except (FileNotFoundError, ValueError) as exc:
        abort(404, f"Failed to load portfolio file: {exc}")

    try:
        result = portfolio_service.calculate(portfolio)
    except PriceFetchError as exc:
        abort(503, f"Failed to calculate portfolio totals: {exc}")

    history_df = history_repository.load()
    
    # If today's data is missing or we are looking at today, we might want to simulate/preview
    # But for now, let's stick to the original logic: simulate if empty or date missing
    if history_df.empty or record_date not in history_df["date"].values:
        # We need a simulate function. 
        # In the original code, simulate_history was in main.py but used in dashboard.
        # We should probably move simulate logic to service or repository.
        # For now, I'll inline a simple simulation or add it to repository.
        # Actually, let's add a simulate method to HistoryRepository or just do it here.
        # The original simulate_history created a temporary dataframe.
        
        # Construct a temporary row
        import pandas as pd
        new_row = {
            "date": record_date,
            "total_usd": round(result.totals.usd, 2),
            "total_twd": round(result.totals.twd, 2),
            "daily_return_pct": 0.0,
        }
        if not history_df.empty:
             history_df = pd.concat([history_df, pd.DataFrame([new_row])], ignore_index=True)
        else:
             history_df = pd.DataFrame([new_row])
             
        # Recalculate returns
        history_df["date"] = pd.to_datetime(history_df["date"])
        history_df.sort_values("date", inplace=True)
        history_df["daily_return_pct"] = history_df["total_usd"].pct_change().fillna(0.0) * 100.0
        history_df["date"] = history_df["date"].dt.strftime("%Y-%m-%d")

    if history_df.empty:
        abort(500, "History dataset is empty.")

    # Get summary for the record date
    # If the record date is simulated, it's in the df.
    # If it's historical, it's in the df.
    try:
        summary_row = history_df[history_df["date"] == record_date].iloc[-1]
    except IndexError:
        # Fallback to last available
        summary_row = history_df.iloc[-1]

    # Calculate advanced metrics
    analysis = analysis_service.analyze_history(history_df)

    chart_labels, chart_totals, chart_returns = _chart_payload(history_df)

    allocation_labels = [pos.name for pos in result.positions if pos.portfolio_pct > 0]
    allocation_data = [round(pos.portfolio_pct, 2) for pos in result.positions if pos.portfolio_pct > 0]

    return render_template(
        "dashboard.html",
        result=result,
        record_date=record_date,
        summary={
            "total_usd": summary_row["total_usd"],
            "total_twd": summary_row["total_twd"],
            "daily_return_pct": summary_row["daily_return_pct"],
        },
        analysis=analysis,
        history_labels=chart_labels,
        history_totals=chart_totals,
        history_returns=chart_returns,
        allocation_labels=allocation_labels,
        allocation_data=allocation_data,
        price_sources=price_fetcher.describe_sources(),
    )

@bp.route("/edit", methods=["GET", "POST"])
def edit_portfolio():
    if request.method == "POST":
        # Process form data
        stocks = []
        symbols = request.form.getlist("stock_symbol[]")
        shares = request.form.getlist("stock_shares[]")
        costs = request.form.getlist("stock_cost[]")
        
        for s, sh, c in zip(symbols, shares, costs):
            if s and sh:
                stocks.append(Stock(
                    symbol=s.strip().upper(),
                    shares=float(sh),
                    average_cost=float(c) if c else 0.0
                ))

        cash_list = []
        currencies = request.form.getlist("cash_currency[]")
        amounts = request.form.getlist("cash_amount[]")
        
        for cur, amt in zip(currencies, amounts):
            if cur and amt:
                cash_list.append(Cash(
                    currency=cur.strip().upper(),
                    amount=float(amt)
                ))

        new_portfolio = Portfolio(stocks=stocks, cash=cash_list)

        try:
            portfolio_repository.save(new_portfolio)
            return redirect(url_for("main.dashboard", date=date.today().isoformat()))
        except Exception as e:
            abort(500, f"Failed to save portfolio: {e}")
            
    # GET request
    try:
        portfolio = portfolio_repository.load()
    except (FileNotFoundError, ValueError):
        portfolio = Portfolio()
        
    # Convert back to dict-like structure for template if needed, 
    # or update template to use objects. 
    # The existing template uses `portfolio.stocks` (list of dicts).
    # Our `Portfolio` object has `stocks` as list of `Stock` objects.
    # Jinja2 can access attributes `stock.symbol` same as `stock['symbol']`? 
    # No, `stock['symbol']` is dict access. `stock.symbol` is attribute access.
    # We need to check the template `edit_portfolio.html`.
    
    return render_template("edit_portfolio.html", portfolio=portfolio)

@bp.route("/healthz")
def healthcheck():
    return "ok", 200
