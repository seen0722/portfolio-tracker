"""Unit tests for the Firstrade CSV → Transaction mapping."""

from datetime import date

from app.domain.transactions import CASH_SYMBOL, Transaction, TxnType
from app.infrastructure.firstrade_importer import (
    _clean_amount,
    _parse_date,
    inject_openings,
    map_row,
)
from app.services.cost_basis import build_positions


def _row(d, kind, qty, sym, price, amt, desc=""):
    return [d, kind, qty, desc, sym, "現金", price, amt]


def test_clean_amount_strips_commas_and_blanks():
    assert _clean_amount("1,195.23") == 1195.23
    assert _clean_amount("-4,474.20") == -4474.20
    assert _clean_amount("") == 0.0


def test_parse_date():
    assert _parse_date("2026/6/18") == date(2026, 6, 18)


def test_buy_maps_to_buy():
    t = map_row(_row("2026/6/11", "買進", "8", "SOXX", "559.2755", "-4,474.20"))
    assert t.txn_type == TxnType.BUY and t.symbol == "SOXX"
    assert t.quantity == 8 and t.price == 559.2755 and t.currency == "USD"


def test_sell_maps_to_sell_with_positive_quantity():
    t = map_row(_row("2026/6/18", "賣出", "-5", "AMZN", "239.05", "1,195.23"))
    assert t.txn_type == TxnType.SELL and t.quantity == 5


def test_deposit_maps_to_cash_deposit():
    t = map_row(_row("2026/2/6", "存款", "0", "", "0.00", "15,000.00"))
    assert t.txn_type == TxnType.DEPOSIT and t.symbol == CASH_SYMBOL and t.quantity == 15000.0


def test_cash_dividend_is_positive_income():
    t = map_row(_row("2026/6/15", "股息", "0", "GOOG", "0.00", "9.93"))
    assert t.txn_type == TxnType.DIVIDEND and t.symbol == "GOOG" and t.quantity == 9.93


def test_interest_maps_to_cash_dividend():
    t = map_row(_row("2026/6/16", "利息收入", "0", "", "0.00", "0.54"))
    assert t.txn_type == TxnType.DIVIDEND and t.symbol == CASH_SYMBOL


def test_negative_dividend_maps_to_withdraw():
    t = map_row(_row("2025/1/2", "股息", "0", "TLT", "0.00", "-124.82"))
    assert t.txn_type == TxnType.WITHDRAW and t.quantity == 124.82


def test_other_reinvest_maps_to_buy_with_derived_price():
    t = map_row(_row("2026/4/1", "其他", "0.00493", "NVDA", "0.00", "-0.87"))
    assert t.txn_type == TxnType.BUY and t.symbol == "NVDA"
    assert abs(t.price - 0.87 / 0.00493) < 1.0  # ≈ 176, derived from amount/qty


def test_other_zero_qty_cash_rebate_maps_to_dividend():
    t = map_row(_row("2026/2/9", "其他", "0", "", "0.00", "25.00"))
    assert t.txn_type == TxnType.DIVIDEND and t.quantity == 25.0


def test_inject_openings_covers_pre_history_oversell():
    # Sold 9 TSLA with no prior buy in the window (legacy holding).
    txns = [
        Transaction(TxnType.SELL, "TSLA", date(2025, 1, 7), quantity=5, price=400, currency="USD"),
        Transaction(TxnType.SELL, "TSLA", date(2025, 2, 3), quantity=4, price=380, currency="USD"),
    ]
    out = inject_openings(txns, date(2025, 1, 1))
    openings = [t for t in out if t.note.startswith("opening")]
    assert len(openings) == 1
    assert openings[0].symbol == "TSLA" and openings[0].quantity == 9
    # The ledger is now self-consistent: build_positions must not raise on oversell.
    state = build_positions(out)
    assert all(p.symbol != "TSLA" for p in state.positions)  # netted to zero
