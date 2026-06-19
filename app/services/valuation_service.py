"""Valuation service — value the ledger-derived positions at current prices.

Reads the transaction ledger, folds it into FIFO positions (cost_basis engine),
then marks them to market and converts currencies, producing the PortfolioResult
shape the dashboard already renders. This is the read path of the "first useful
app": real cost basis + P&L instead of the old mutable snapshot.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from currency_converter import CurrencyConverter

from app.domain.positions import Position
from app.domain.models import PortfolioResult, PositionBreakdown, Totals
from app.domain.protocols import LedgerRepository, MarketDataProvider
from app.infrastructure.market_data import PriceFetchError
from app.services.cost_basis import build_positions

logger = logging.getLogger(__name__)

_CASH_CATEGORY = "cash"
_STOCK_CATEGORY = "stock"


class ValuationService:
    """Turn the ledger into a priced PortfolioResult."""

    def __init__(
        self,
        ledger: LedgerRepository,
        price_provider: MarketDataProvider,
        converter: Optional[CurrencyConverter] = None,
    ) -> None:
        self.ledger = ledger
        self.price_provider = price_provider
        self.converter = converter or CurrencyConverter(
            fallback_on_missing_rate=True,
            fallback_on_wrong_date=True,
        )

    def value(self) -> PortfolioResult:
        state = build_positions(self.ledger.all())
        totals = Totals()
        positions: List[PositionBreakdown] = []

        symbols = [pos.symbol for pos in state.positions]
        prices = self.price_provider.get_prices(symbols) if symbols else {}

        for pos in state.positions:
            # Missing price -> fall back to average cost so the row still renders
            # (unrealized P&L shows 0 rather than crashing the page).
            price = prices.get(pos.symbol)
            if price is None:
                price = pos.average_cost
            breakdown, usd, twd, cost_usd, cost_twd = self._value_position(pos, price)
            totals.add(usd, twd, cost_usd, cost_twd)
            positions.append(breakdown)

        for currency, amount in sorted(state.cash.items()):
            if abs(amount) < 1e-9:
                continue
            breakdown, usd, twd, cost_usd, cost_twd = self._value_cash(currency, amount)
            totals.add(usd, twd, cost_usd, cost_twd)
            positions.append(breakdown)

        total_value_usd = totals.usd or 1.0
        for breakdown in positions:
            breakdown.portfolio_pct = breakdown.value_usd / total_value_usd * 100.0

        return PortfolioResult(totals=totals, positions=positions)

    def _value_position(
        self, pos: Position, price: float
    ) -> Tuple[PositionBreakdown, float, float, float, float]:
        currency = pos.currency
        if currency == "TWD":
            value_twd = price * pos.quantity
            value_usd = self._convert(value_twd, "TWD", "USD")
            cost_twd = pos.total_cost
            cost_usd = self._convert(cost_twd, "TWD", "USD")
        else:
            value_usd = price * pos.quantity
            value_twd = self._convert(value_usd, "USD", "TWD")
            cost_usd = pos.total_cost
            cost_twd = self._convert(cost_usd, "USD", "TWD")

        unrealized_pl_usd = value_usd - cost_usd
        unrealized_pl_twd = value_twd - cost_twd
        roi_pct = (unrealized_pl_usd / cost_usd * 100.0) if cost_usd else 0.0

        breakdown = PositionBreakdown(
            name=pos.symbol,
            category=_STOCK_CATEGORY,
            value_usd=value_usd,
            value_twd=value_twd,
            portfolio_pct=0.0,
            quantity=pos.quantity,
            unit_price=price,
            price_currency=currency,
            average_cost=pos.average_cost,
            total_cost_usd=cost_usd,
            total_cost_twd=cost_twd,
            unrealized_pl_usd=unrealized_pl_usd,
            unrealized_pl_twd=unrealized_pl_twd,
            roi_pct=roi_pct,
        )
        return breakdown, value_usd, value_twd, cost_usd, cost_twd

    def _value_cash(
        self, currency: str, amount: float
    ) -> Tuple[PositionBreakdown, float, float, float, float]:
        value_usd = self._convert(amount, currency, "USD")
        value_twd = self._convert(amount, currency, "TWD")
        breakdown = PositionBreakdown(
            name=currency,
            category=_CASH_CATEGORY,
            value_usd=value_usd,
            value_twd=value_twd,
            portfolio_pct=0.0,
            quantity=amount,
            unit_price=None,
            price_currency=currency,
            average_cost=None,
            total_cost_usd=value_usd,
            total_cost_twd=value_twd,
            unrealized_pl_usd=0.0,
            unrealized_pl_twd=0.0,
            roi_pct=0.0,
        )
        return breakdown, value_usd, value_twd, value_usd, value_twd

    def _convert(self, amount: float, source: str, target: str) -> float:
        if source == target:
            return amount
        try:
            converted = self.converter.convert(amount, source, target)
            if converted is not None:
                return float(converted)
        except Exception as exc:  # offline ECB table may lack a pair
            logger.debug("CurrencyConverter failed (%s -> %s): %s", source, target, exc)

        pair = f"{source}{target}=X"
        try:
            rate = self.price_provider.get_price(pair)
        except PriceFetchError as exc:
            raise PriceFetchError(f"FX conversion {source}->{target} failed") from exc
        return amount * rate
