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

# Chart time-range tab key -> yfinance period for NAV reconstruction.
NAV_RANGES = {"1w": "5d", "1m": "1mo", "3m": "3mo", "6m": "6mo", "1y": "1y", "2y": "2y"}

# Donut/legend/holdings-row colour palette (shared, single source of truth).
ALLOC_PALETTE = [
    "#2350e8", "#07976a", "#c5860f", "#8b5cf6", "#ec4899",
    "#06b6d4", "#64748b", "#f97316", "#14b8a6", "#a855f7",
]


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

    # Allocation donut is the "股票/ETFs" view — exclude cash, and weight each
    # holding by its share of the stock/ETF total (not the cash-inclusive total).
    _alloc = sorted(
        (pos for pos in result.positions if pos.category == "stock" and pos.value_usd > 0),
        key=lambda pos: pos.value_usd,
        reverse=True,
    )
    _stock_total = sum(pos.value_usd for pos in _alloc) or 1.0
    allocation_labels = [pos.name for pos in _alloc]
    allocation_values = [round(pos.value_usd, 2) for pos in _alloc]
    allocation_data = [round(pos.value_usd / _stock_total * 100, 2) for pos in _alloc]
    # Shared palette so the donut, its legend, and the holdings-table row dots all
    # use the same colour per symbol — visually linking allocation to holdings.
    allocation_colors = {pos.name: ALLOC_PALETTE[i % len(ALLOC_PALETTE)] for i, pos in enumerate(_alloc)}

    return render_template(
        "dashboard.html",
        result=result,
        record_date=record_date,
        summary={
            "total_usd": result.totals.usd,
            "total_twd": result.totals.twd,
            "daily_return_pct": daily_return,
            # Exact today's $ change: total − yesterday's total (derived from the
            # daily return), so the hero shows "+$X (+Y%)" like Firstrade.
            "daily_change_usd": (
                result.totals.usd - result.totals.usd / (1 + daily_return / 100)
                if daily_return
                else 0.0
            ),
        },
        analysis=analysis,
        history_labels=chart_labels,
        history_totals=chart_totals,
        history_returns=chart_returns,
        allocation_labels=allocation_labels,
        allocation_data=allocation_data,
        allocation_values=allocation_values,
        allocation_colors=allocation_colors,
        allocation_palette=ALLOC_PALETTE,
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


@bp.route("/nav.json")
def nav_json():
    """NAV series for a chart time-range tab (1w/1m/3m/6m/1y/2y)."""
    period = NAV_RANGES.get(request.args.get("range", "3m"), "3mo")
    df = container.nav_service.series_for(period)
    if df.empty:
        return jsonify({"labels": [], "totals": []})
    totals = [None if pd.isna(v) else round(float(v), 2) for v in df["total_usd"].tolist()]
    return jsonify({"labels": df["date"].tolist(), "totals": totals})


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


@bp.route("/macro.json")
def macro():
    """Market-wide regime: macro indicators + composite Risk-On/Off read."""
    return jsonify(container.macro_provider.regime().to_dict())


@bp.route("/calendar.json")
def calendar():
    """Upcoming high-impact macro events (FOMC / CPI / NFP) with countdowns."""
    from app.services.economic_calendar import EconomicCalendar

    events = EconomicCalendar().upcoming(limit=5)
    return jsonify([e.to_dict() for e in events])


@bp.route("/correlation.json")
def correlation():
    """Factor correlation for a target (portfolio or symbol)."""
    target = request.args.get("target", "portfolio")
    factor = request.args.get("factor")
    return jsonify(container.factor_analysis.analyze(target=target, factor=factor))


@bp.route("/heatmap.json")
def heatmap():
    """Multi-horizon performance heatmap across factors, indices, sectors, holdings."""
    from app.services.performance_heatmap import HORIZONS

    state = build_positions(container.ledger.all())
    holdings = [pos.symbol for pos in state.positions]
    return jsonify({
        "horizons": [{"key": k, "label": label} for k, label in HORIZONS],
        "groups": container.performance_heatmap.build(holdings),
    })


MACRO_WHY = {
    "VIX": "市場恐慌與避險情緒;VIX 走高代表風險趨避,壓抑成長股估值。",
    "HYOAS": "高收益債信用利差;走擴代表風險胃納下降,常領先股市轉弱。",
    "T10Y2Y": "10Y 減 2Y 殖利率;倒掛(負值)是經典衰退前兆。",
    "REAL10Y": "扣除通膨後的實質利率;成長股是長天期資產,實質利率走高最傷估值。",
    "US10Y": "無風險折現率基準;殖利率上行壓抑高本益比的科技股。",
    "DXY": "美元強弱;強美元不利大型跨國科技股的海外營收。",
    "SOX": "費城半導體指數;直接反映你重押的 NVDA 等半導體景氣。",
    "GOLD": "避險與抗通膨資產;金價急漲常伴隨風險趨避。",
    "WTI": "原油價格;油價上行推升通膨,間接壓抑寬鬆預期。",
}


@bp.route("/macro")
def macro_page():
    """Full market-regime page: factors with explanations + event calendar."""
    from app.services.economic_calendar import EconomicCalendar

    regime = container.macro_provider.regime()
    events = EconomicCalendar().upcoming(limit=6)
    state = build_positions(container.ledger.all())
    holdings = [pos.symbol for pos in state.positions]
    return render_template(
        "macro.html",
        regime=regime.to_dict(),
        events=[e.to_dict() for e in events],
        why=MACRO_WHY,
        holdings=holdings,
    )


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
