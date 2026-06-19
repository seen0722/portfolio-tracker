"""Unit tests for the SQLite transaction ledger."""

from datetime import date

import pytest

from app.domain.transactions import Transaction, TxnType
from app.infrastructure.ledger import SqliteLedger


@pytest.fixture
def ledger():
    led = SqliteLedger(":memory:")
    yield led
    led.close()


def test_add_assigns_id_and_roundtrips(ledger):
    saved = ledger.add(
        Transaction(TxnType.BUY, "NVDA", date(2026, 1, 2), quantity=10, price=100)
    )
    assert saved.id is not None

    rows = ledger.all()
    assert len(rows) == 1
    got = rows[0]
    assert got.symbol == "NVDA"
    assert got.txn_type == TxnType.BUY
    assert got.quantity == 10
    assert got.price == 100
    assert got.trade_date == date(2026, 1, 2)


def test_by_symbol_filters_and_orders_by_date(ledger):
    ledger.add_many(
        [
            Transaction(TxnType.BUY, "NVDA", date(2026, 1, 3), quantity=5, price=100),
            Transaction(TxnType.BUY, "NVDA", date(2026, 1, 1), quantity=5, price=90),
            Transaction(TxnType.BUY, "GOOG", date(2026, 1, 2), quantity=2, price=150),
        ]
    )
    nvda = ledger.by_symbol("NVDA")
    assert [t.trade_date for t in nvda] == [date(2026, 1, 1), date(2026, 1, 3)]
    assert ledger.symbols() == ["GOOG", "NVDA"]


def test_corporate_action_split_roundtrips(ledger):
    ledger.add(Transaction(TxnType.SPLIT, "NVDA", date(2026, 6, 10), ratio=4.0, note="4-for-1"))
    got = ledger.by_symbol("NVDA")[0]
    assert got.txn_type == TxnType.SPLIT
    assert got.ratio == 4.0
    assert got.note == "4-for-1"


def test_merger_keeps_related_symbol(ledger):
    ledger.add(Transaction(TxnType.TICKER_CHANGE, "FB", date(2022, 6, 9), related_symbol="META"))
    got = ledger.by_symbol("FB")[0]
    assert got.related_symbol == "META"


def test_delete_and_count(ledger):
    saved = ledger.add(
        Transaction(TxnType.BUY, "NVDA", date(2026, 1, 2), quantity=10, price=100)
    )
    assert ledger.count() == 1
    ledger.delete(saved.id)
    assert ledger.count() == 0


def test_persists_to_file(tmp_path):
    db = tmp_path / "portfolio.db"
    led = SqliteLedger(db)
    led.add(Transaction(TxnType.BUY, "NVDA", date(2026, 1, 2), quantity=10, price=100))
    led.close()

    reopened = SqliteLedger(db)
    assert reopened.count() == 1
    reopened.close()
