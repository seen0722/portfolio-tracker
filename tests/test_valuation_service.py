"""Unit tests for the ledger-based valuation service."""

from datetime import date

import pytest

from app.domain.transactions import CASH_SYMBOL, Transaction, TxnType
from app.infrastructure.ledger import SqliteLedger
from app.services.valuation_service import ValuationService


class FakeProvider:
    """Deterministic price source for tests (no network)."""

    def __init__(self, prices):
        self.prices = prices

    def get_price(self, symbol):
        return self.prices[symbol]

    def get_prices(self, symbols):
        return {s: self.prices[s] for s in symbols if s in self.prices}


@pytest.fixture
def ledger():
    led = SqliteLedger(":memory:")
    yield led
    led.close()


def test_values_positions_and_cash_from_ledger(ledger):
    ledger.add_many(
        [
            Transaction(TxnType.DEPOSIT, CASH_SYMBOL, date(2026, 1, 1), quantity=5000, currency="USD"),
            Transaction(TxnType.BUY, "NVDA", date(2026, 1, 2), quantity=10, price=100, currency="USD"),
        ]
    )
    # ECB CurrencyConverter lacks TWD, so USD->TWD resolves via the FX pair
    # the price provider supplies (mirrors production's Yahoo USDTWD=X fetch).
    svc = ValuationService(ledger, FakeProvider({"NVDA": 150, "USDTWD=X": 32.0}))
    result = svc.value()

    nvda = next(p for p in result.positions if p.name == "NVDA")
    assert nvda.quantity == 10
    assert nvda.unit_price == 150
    assert nvda.value_usd == pytest.approx(1500)
    assert nvda.total_cost_usd == pytest.approx(1000)
    assert nvda.unrealized_pl_usd == pytest.approx(500)
    assert nvda.roi_pct == pytest.approx(50)

    # cash = 5000 deposited - 1000 spent on NVDA
    cash = next(p for p in result.positions if p.category == "cash")
    assert cash.value_usd == pytest.approx(4000)

    # total = 1500 (NVDA) + 4000 (cash); unrealized only from NVDA
    assert result.totals.usd == pytest.approx(5500)
    assert result.totals.unrealized_pl_usd == pytest.approx(500)


def test_portfolio_pct_sums_to_100(ledger):
    ledger.add_many(
        [
            Transaction(TxnType.DEPOSIT, CASH_SYMBOL, date(2026, 1, 1), quantity=5000, currency="USD"),
            Transaction(TxnType.BUY, "AAA", date(2026, 1, 1), quantity=10, price=100, currency="USD"),
            Transaction(TxnType.BUY, "BBB", date(2026, 1, 1), quantity=10, price=100, currency="USD"),
        ]
    )
    svc = ValuationService(ledger, FakeProvider({"AAA": 100, "BBB": 100, "USDTWD=X": 32.0}))
    result = svc.value()
    assert sum(p.portfolio_pct for p in result.positions) == pytest.approx(100)


def test_missing_price_falls_back_to_average_cost(ledger):
    ledger.add(Transaction(TxnType.BUY, "ZZZ", date(2026, 1, 1), quantity=5, price=20, currency="USD"))
    svc = ValuationService(ledger, FakeProvider({"USDTWD=X": 32.0}))  # ZZZ price absent
    result = svc.value()
    pos = next(p for p in result.positions if p.name == "ZZZ")
    assert pos.unit_price == pytest.approx(20)
    assert pos.unrealized_pl_usd == pytest.approx(0)
