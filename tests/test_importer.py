"""Unit tests for the portfolio.json -> transactions importer."""

import json
from datetime import date

from app.domain.transactions import CASH_SYMBOL, TxnType
from app.infrastructure.importer import (
    import_portfolio_json,
    transactions_from_portfolio_dict,
    verify_import,
)
from app.infrastructure.ledger import SqliteLedger

SAMPLE = {
    "stocks": [
        {"symbol": "NVDA", "shares": 67.0, "average_cost": 188.14},
        {"symbol": "00795B.TWO", "shares": 26000.0, "average_cost": 27.24},
        {"symbol": "ZERO", "shares": 0.0, "average_cost": 5.0},
    ],
    "cash": [
        {"currency": "USD", "amount": 70.64},
        {"currency": "TWD", "amount": 0.0},
    ],
}


def test_maps_stocks_to_buys_with_correct_currency():
    txns = transactions_from_portfolio_dict(SAMPLE)
    buys = [t for t in txns if t.txn_type == TxnType.BUY]
    # zero-share holding is skipped
    assert {t.symbol for t in buys} == {"NVDA", "00795B.TWO"}

    tw = next(t for t in buys if t.symbol == "00795B.TWO")
    us = next(t for t in buys if t.symbol == "NVDA")
    assert tw.currency == "TWD"
    assert us.currency == "USD"
    assert us.quantity == 67.0
    assert us.price == 188.14


def test_opening_deposits_make_net_cash_equal_reported():
    # After the seed buys draw down the opening deposits, net cash per currency
    # must equal the reported cash (USD 70.64, TWD 0) — no spurious deficit.
    import pytest

    from app.services.cost_basis import build_positions

    txns = transactions_from_portfolio_dict(SAMPLE)
    deposits = [t for t in txns if t.txn_type == TxnType.DEPOSIT]
    assert {d.currency for d in deposits} == {"USD", "TWD"}
    assert all(d.symbol == CASH_SYMBOL for d in deposits)

    state = build_positions(txns)
    assert state.cash["USD"] == pytest.approx(70.64)
    assert state.cash.get("TWD", 0.0) == pytest.approx(0.0)


def test_verify_import_passes_for_consistent_mapping():
    txns = transactions_from_portfolio_dict(SAMPLE)
    assert verify_import(SAMPLE, txns) == []


def test_import_portfolio_json_loads_into_ledger(tmp_path):
    path = tmp_path / "portfolio.json"
    path.write_text(json.dumps(SAMPLE), encoding="utf-8")

    led = SqliteLedger(":memory:")
    summary = import_portfolio_json(path, led, trade_date=date(2020, 1, 1))
    assert summary["verified"] is True
    assert summary["imported"] == 4  # 2 opening deposits (USD, TWD) + 2 buys
    assert led.count() == 4
    led.close()
