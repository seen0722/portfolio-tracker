"""Portfolio valuation service."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Tuple

from currency_converter import CurrencyConverter

from app.domain.models import (
    Portfolio,
    PortfolioResult,
    PositionBreakdown,
    Totals,
    Stock,
    Cash
)
from app.infrastructure.market_data import PriceFetchError, PriceFetcher

logger = logging.getLogger(__name__)


class PortfolioService:
    """Calculate portfolio totals with currency conversion."""

    def __init__(self, price_fetcher: PriceFetcher) -> None:
        self.price_fetcher = price_fetcher
        self.converter = CurrencyConverter(
            fallback_on_missing_rate=True,
            fallback_on_wrong_date=True,
        )

    def calculate(self, portfolio: Portfolio) -> PortfolioResult:
        totals = Totals()
        positions: List[PositionBreakdown] = []
        
        # Collect all symbols to fetch
        stock_symbols = [s.symbol for s in portfolio.stocks]
        # Cash currencies also need rates (e.g. USD=X, TWD=X, or pairs like USDTWD=X)
        # The current implementation of _convert uses get_price internally.
        # To fully optimize, we should pre-fetch currency pairs too.
        # For now, let's optimize stocks first as they are the main latency source.
        
        prices = self.price_fetcher.get_prices(stock_symbols)
        
        for stock in portfolio.stocks:
            # Pass pre-fetched price to _value_stock if possible, or let it use cache
            # Since we populated the cache in get_prices, _value_stock calling get_price 
            # will hit the cache instantly.
            usd, twd, cost_usd, cost_twd, breakdown = self._value_stock(stock)
            totals.add(usd, twd, cost_usd, cost_twd)
            positions.append(breakdown)

        for cash in portfolio.cash:
            usd, twd, cost_usd, cost_twd, breakdown = self._value_cash(cash)
            totals.add(usd, twd, cost_usd, cost_twd)
            positions.append(breakdown)

        total_value_usd = totals.usd or 1.0  # avoid divide-by-zero
        for pos in positions:
            pos.portfolio_pct = (pos.value_usd / total_value_usd) * 100.0

        return PortfolioResult(totals=totals, positions=positions)

    def _value_stock(self, stock: Stock) -> Tuple[float, float, float, float, PositionBreakdown]:
        symbol = stock.symbol
        shares = stock.shares
        average_cost = stock.average_cost
        price = self.price_fetcher.get_price(symbol)

        price_currency = "TWD" if ".TW" in symbol.upper() else "USD"
        if ".TW" in symbol.upper():
            value_twd = price * shares
            value_usd = self._convert(value_twd, "TWD", "USD")
            
            total_cost_twd = average_cost * shares
            total_cost_usd = self._convert(total_cost_twd, "TWD", "USD")
        else:
            value_usd = price * shares
            value_twd = self._convert(value_usd, "USD", "TWD")
            
            total_cost_usd = average_cost * shares
            total_cost_twd = self._convert(total_cost_usd, "USD", "TWD")

        unrealized_pl_usd = value_usd - total_cost_usd
        unrealized_pl_twd = value_twd - total_cost_twd
        roi_pct = (unrealized_pl_usd / total_cost_usd * 100.0) if total_cost_usd else 0.0

        breakdown = PositionBreakdown(
            name=symbol,
            category="stock",
            value_usd=value_usd,
            value_twd=value_twd,
            portfolio_pct=0.0,
            quantity=shares,
            unit_price=price,
            price_currency=price_currency,
            average_cost=average_cost,
            total_cost_usd=total_cost_usd,
            total_cost_twd=total_cost_twd,
            unrealized_pl_usd=unrealized_pl_usd,
            unrealized_pl_twd=unrealized_pl_twd,
            roi_pct=roi_pct,
        )
        return value_usd, value_twd, total_cost_usd, total_cost_twd, breakdown

    def _value_cash(self, cash: Cash) -> Tuple[float, float, float, float, PositionBreakdown]:
        currency = cash.currency.upper()
        amount = cash.amount
        value_usd = self._convert(amount, currency, "USD")
        value_twd = self._convert(amount, currency, "TWD")
        
        # Cash has no "cost" in the investment sense, so cost = value (0% ROI)
        cost_usd = value_usd
        cost_twd = value_twd

        breakdown = PositionBreakdown(
            name=currency,
            category="cash",
            value_usd=value_usd,
            value_twd=value_twd,
            portfolio_pct=0.0,
            quantity=amount,
            unit_price=None,
            price_currency=currency,
            average_cost=None,
            total_cost_usd=cost_usd,
            total_cost_twd=cost_twd,
            unrealized_pl_usd=0.0,
            unrealized_pl_twd=0.0,
            roi_pct=0.0,
        )
        return value_usd, value_twd, cost_usd, cost_twd, breakdown

    def _convert(self, amount: float, source: str, target: str) -> float:
        if source == target:
            return amount
        try:
            converted = self.converter.convert(amount, source, target)
            if converted is not None:
                return float(converted)
        except Exception as exc:
            logger.debug("CurrencyConverter failed (%s -> %s): %s", source, target, exc)

        pair = f"{source}{target}=X"
        try:
            rate = self.price_fetcher.get_price(pair)
        except PriceFetchError as exc:
            raise PriceFetchError(f"FX conversion {source}->{target} failed") from exc

        return amount * rate
