"""Web routes."""

from __future__ import annotations

import math
from dataclasses import asdict
from datetime import date

import pandas as pd
from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from app.dependencies import container
from app.domain.transactions import CASH_SYMBOL, Transaction, TxnType
from app.infrastructure.market_data import PriceFetchError
from app.services.cost_basis import build_positions

bp = Blueprint("main", __name__)

MAX_HISTORY_POINTS = 90


def _chart_payload(history_df):
    limited = history_df.tail(MAX_HISTORY_POINTS)
    labels = limited["date"].tolist()

    def clean_val(value):
        return None if pd.isna(value) or math.isnan(value) or math.isinf(value) else round(value, 2)

    totals = [clean_val(value) for value in limited["total_usd"].tolist()]
    returns = [clean_val(value) for value in limited["daily_return_pct"].tolist()]
    return labels, totals, returns


@bp.route("/")
def dashboard():
    record_date = request.args.get("date") or date.today().isoformat()

    try:
        result = container.valuation_service.value()
    except PriceFetchError as exc:
        abort(503, f"Failed to value portfolio: {exc}")

    # Real NAV series: reconstruct from historical closes on first load, then
    # record today's live point. Replaces the old simulated-history hack.
    nav = container.nav_service
    nav.ensure_history()
    nav.snapshot(result.totals.usd, result.totals.twd, date.today().isoformat())
    history_df = nav.history()

    daily_return = (
        float(history_df["daily_return_pct"].iloc[-1]) if not history_df.empty else 0.0
    )
    analysis = container.analysis_service.analyze_history(history_df)
    chart_labels, chart_totals, chart_returns = (
        _chart_payload(history_df) if not history_df.empty else ([], [], [])
    )

    allocation_labels = [pos.name for pos in result.positions if pos.portfolio_pct > 0]
    allocation_data = [round(pos.portfolio_pct, 2) for pos in result.positions if pos.portfolio_pct > 0]

    return render_template(
        "dashboard.html",
        result=result,
        record_date=record_date,
        summary={
            "total_usd": result.totals.usd,
            "total_twd": result.totals.twd,
            "daily_return_pct": daily_return,
        },
        analysis=analysis,
        history_labels=chart_labels,
        history_totals=chart_totals,
        history_returns=chart_returns,
        allocation_labels=allocation_labels,
        allocation_data=allocation_data,
        price_sources=container.price_fetcher.describe_sources(),
    )


@bp.route("/transactions", methods=["GET", "POST"])
def transactions():
    if request.method == "POST":
        symbol = (request.form.get("symbol") or "").strip().upper() or CASH_SYMBOL
        txn = Transaction(
            txn_type=TxnType(request.form["txn_type"]),
            symbol=symbol,
            trade_date=date.fromisoformat(request.form["trade_date"]),
            quantity=float(request.form.get("quantity") or 0),
            price=float(request.form.get("price") or 0),
            fee=float(request.form.get("fee") or 0),
            currency=(request.form.get("currency") or "USD").strip().upper(),
            related_symbol=(request.form.get("related_symbol") or "").strip().upper(),
            ratio=float(request.form.get("ratio") or 0),
            note=(request.form.get("note") or "").strip(),
        )
        container.ledger.add(txn)
        return redirect(url_for("main.transactions"))

    txns = list(reversed(container.ledger.all()))
    return render_template(
        "transactions.html",
        transactions=txns,
        txn_types=[t.value for t in TxnType],
        today=date.today().isoformat(),
    )


@bp.route("/transactions/<int:txn_id>/delete", methods=["POST"])
def delete_transaction(txn_id: int):
    container.ledger.delete(txn_id)
    return redirect(url_for("main.transactions"))


@bp.route("/capex.json")
def capex_signals():
    """Auto-computed AI capex signals for the watch-list."""
    symbols_arg = request.args.get("symbols")
    symbols = (
        [s.strip().upper() for s in symbols_arg.split(",") if s.strip()]
        if symbols_arg
        else None
    )
    signals = container.capex_service.collect(symbols)
    return jsonify([asdict(signal) for signal in signals])


@bp.route("/signals.json")
def signals():
    """Deterministic EvidenceBundles for the current holdings."""
    symbols_arg = request.args.get("symbols")
    if symbols_arg:
        symbols = [s.strip().upper() for s in symbols_arg.split(",") if s.strip()]
    else:
        state = build_positions(container.ledger.all())
        symbols = [pos.symbol for pos in state.positions]
    bundles = container.signal_orchestrator.bundles_for(symbols)
    return jsonify({sym: bundle.to_dict() for sym, bundle in bundles.items()})


@bp.route("/advice.json")
def advice():
    """Read-only, guardrailed opinion cards for the current holdings."""
    symbols_arg = request.args.get("symbols")
    if symbols_arg:
        symbols = [s.strip().upper() for s in symbols_arg.split(",") if s.strip()]
        contexts = {}
    else:
        result = container.valuation_service.value()
        stock_positions = [p for p in result.positions if p.category == "stock"]
        symbols = [p.name for p in stock_positions]
        contexts = {
            p.name: {"roi_pct": p.roi_pct, "unrealized_pl_usd": p.unrealized_pl_usd}
            for p in stock_positions
        }
    cards = container.advice_service.advise_many(symbols, contexts)
    return jsonify({sym: card.to_dict() for sym, card in cards.items()})


@bp.route("/report")
def report_preview():
    """HTML preview of the daily report (same content the scheduler pushes)."""
    report = container.report_service.generate()
    return render_template("report.html", report=report.summary, title=report.title)


@bp.route("/report.json")
def report_json():
    return jsonify(container.report_service.generate().summary)


@bp.route("/healthz")
def healthcheck():
    return "ok", 200
