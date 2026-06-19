"""Unit tests for the FIFO cost-basis engine — the correctness core."""

from datetime import date

import pytest

from app.domain.transactions import CASH_SYMBOL, Transaction, TxnType
from app.services.cost_basis import build_positions


def _buy(symbol, qty, price, day, fee=0.0, currency="USD"):
    return Transaction(TxnType.BUY, symbol, date(2026, 1, day), quantity=qty, price=price, fee=fee, currency=currency)


def _sell(symbol, qty, price, day, fee=0.0, currency="USD"):
    return Transaction(TxnType.SELL, symbol, date(2026, 1, day), quantity=qty, price=price, fee=fee, currency=currency)


def test_single_buy_creates_one_position():
    state = build_positions([_buy("NVDA", 10, 100, 1)])
    assert len(state.positions) == 1
    pos = state.positions[0]
    assert pos.symbol == "NVDA"
    assert pos.quantity == 10
    assert pos.average_cost == pytest.approx(100)
    assert pos.total_cost == pytest.approx(1000)
    assert state.cash["USD"] == pytest.approx(-1000)


def test_buy_fee_is_folded_into_cost_basis():
    state = build_positions([_buy("NVDA", 10, 100, 1, fee=10)])
    pos = state.positions[0]
    assert pos.total_cost == pytest.approx(1010)
    assert pos.average_cost == pytest.approx(101)
    assert state.cash["USD"] == pytest.approx(-1010)


def test_two_buys_give_weighted_average_cost():
    state = build_positions([_buy("NVDA", 10, 100, 1), _buy("NVDA", 10, 120, 2)])
    pos = state.positions[0]
    assert pos.quantity == 20
    assert pos.average_cost == pytest.approx(110)
    assert pos.total_cost == pytest.approx(2200)


def test_fifo_sell_realizes_from_oldest_lot():
    txns = [_buy("NVDA", 10, 100, 1), _buy("NVDA", 10, 120, 2), _sell("NVDA", 5, 150, 3)]
    state = build_positions(txns)
    pos = state.positions[0]
    # sold 5 oldest @100 -> realized = 5*150 - 5*100 = 250
    assert pos.realized_pl == pytest.approx(250)
    # remaining: 5 @100 + 10 @120 = 15 shares, cost 1700
    assert pos.quantity == 15
    assert pos.total_cost == pytest.approx(1700)
    assert pos.average_cost == pytest.approx(1700 / 15)


def test_sell_fee_reduces_realized_pnl():
    txns = [_buy("NVDA", 10, 100, 1), _sell("NVDA", 10, 150, 2, fee=5)]
    state = build_positions(txns)
    # position fully closed -> not in positions list
    assert state.positions == []
    # realized = (10*150 - 5) - 10*100 = 495
    assert state.realized_pl["USD"] == pytest.approx(495)


def test_oversell_raises():
    with pytest.raises(ValueError):
        build_positions([_buy("NVDA", 10, 100, 1), _sell("NVDA", 11, 150, 2)])


def test_split_scales_shares_and_preserves_total_cost():
    txns = [
        _buy("NVDA", 10, 100, 1),
        Transaction(TxnType.SPLIT, "NVDA", date(2026, 1, 5), ratio=4.0),
    ]
    state = build_positions(txns)
    pos = state.positions[0]
    assert pos.quantity == pytest.approx(40)
    assert pos.average_cost == pytest.approx(25)
    assert pos.total_cost == pytest.approx(1000)


def test_ticker_change_moves_position_to_new_symbol():
    txns = [
        Transaction(TxnType.BUY, "FB", date(2022, 1, 1), quantity=10, price=200),
        Transaction(TxnType.TICKER_CHANGE, "FB", date(2022, 6, 9), related_symbol="META"),
    ]
    state = build_positions(txns)
    assert len(state.positions) == 1
    assert state.positions[0].symbol == "META"
    assert state.positions[0].quantity == 10
    assert state.positions[0].total_cost == pytest.approx(2000)


def test_cash_tracks_deposits_buys_sells_and_dividends():
    txns = [
        Transaction(TxnType.DEPOSIT, CASH_SYMBOL, date(2026, 1, 1), quantity=10000),
        _buy("NVDA", 10, 100, 2),  # -1000
        _sell("NVDA", 5, 150, 3),  # +750
        Transaction(TxnType.DIVIDEND, "NVDA", date(2026, 1, 4), quantity=20),  # +20
    ]
    state = build_positions(txns)
    assert state.cash["USD"] == pytest.approx(10000 - 1000 + 750 + 20)


def test_multi_currency_cash_kept_separate():
    txns = [
        Transaction(TxnType.DEPOSIT, CASH_SYMBOL, date(2026, 1, 1), quantity=5000, currency="USD"),
        Transaction(TxnType.DEPOSIT, CASH_SYMBOL, date(2026, 1, 1), quantity=100000, currency="TWD"),
        _buy("00795B.TWO", 1000, 27, 2, currency="TWD"),
    ]
    state = build_positions(txns)
    assert state.cash["USD"] == pytest.approx(5000)
    assert state.cash["TWD"] == pytest.approx(100000 - 27000)
    tw_pos = next(p for p in state.positions if p.symbol == "00795B.TWO")
    assert tw_pos.currency == "TWD"
