"""Unit tests for the pure Transaction domain model."""

from datetime import date

from app.domain.transactions import CASH_SYMBOL, Transaction, TxnType


def test_buy_cash_delta_is_negative_cost_plus_fee():
    txn = Transaction(TxnType.BUY, "NVDA", date(2026, 1, 2), quantity=10, price=100, fee=1)
    assert txn.cash_delta == -(10 * 100 + 1)


def test_sell_cash_delta_is_proceeds_minus_fee():
    txn = Transaction(TxnType.SELL, "NVDA", date(2026, 1, 2), quantity=10, price=120, fee=1)
    assert txn.cash_delta == (10 * 120 - 1)


def test_deposit_and_dividend_add_cash():
    deposit = Transaction(TxnType.DEPOSIT, CASH_SYMBOL, date(2026, 1, 2), quantity=500)
    dividend = Transaction(TxnType.DIVIDEND, "NVDA", date(2026, 1, 2), quantity=12)
    assert deposit.cash_delta == 500
    assert dividend.cash_delta == 12


def test_withdraw_removes_cash():
    txn = Transaction(TxnType.WITHDRAW, CASH_SYMBOL, date(2026, 1, 2), quantity=200)
    assert txn.cash_delta == -200


def test_corporate_actions_have_no_cash_delta():
    split = Transaction(TxnType.SPLIT, "NVDA", date(2026, 1, 2), ratio=4.0)
    merger = Transaction(TxnType.MERGER, "FB", date(2022, 6, 9), related_symbol="META")
    assert split.cash_delta == 0.0
    assert merger.cash_delta == 0.0


def test_transaction_is_immutable():
    txn = Transaction(TxnType.BUY, "NVDA", date(2026, 1, 2), quantity=10, price=100)
    try:
        txn.quantity = 20  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("Transaction should be frozen/immutable")
