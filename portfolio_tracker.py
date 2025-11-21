"""Portfolio valuation utilities."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from currency_converter import CurrencyConverter

from price_fetcher import PriceFetchError, PriceFetcher

logger = logging.getLogger(__name__)


@dataclass
class Totals:
    usd: float = 0.0
    twd: float = 0.0
    cost_usd: float = 0.0
    cost_twd: float = 0.0
    unrealized_pl_usd: float = 0.0
    unrealized_pl_twd: float = 0.0
    roi_pct: float = 0.0

    def add(self, usd: float, twd: float, cost_usd: float, cost_twd: float) -> None:
        self.usd += usd
        self.twd += twd
        self.cost_usd += cost_usd
        self.cost_twd += cost_twd
        self.unrealized_pl_usd = self.usd - self.cost_usd
        self.unrealized_pl_twd = self.twd - self.cost_twd
        self.roi_pct = (self.unrealized_pl_usd / self.cost_usd * 100.0) if self.cost_usd else 0.0


@dataclass
class PositionBreakdown:
    name: str
    category: str
    value_usd: float
    value_twd: float
    portfolio_pct: float
    quantity: float | None = None
    unit_price: float | None = None
    price_currency: str | None = None
    average_cost: float | None = None
    total_cost_usd: float = 0.0
    total_cost_twd: float = 0.0
    unrealized_pl_usd: float = 0.0
    unrealized_pl_twd: float = 0.0
    roi_pct: float = 0.0


@dataclass
class PortfolioResult:
    totals: Totals
    positions: List[PositionBreakdown]


class PortfolioCalculator:
    """Calculate portfolio totals with currency conversion."""

    def __init__(self, price_fetcher: PriceFetcher) -> None:
        self.price_fetcher = price_fetcher
        self.converter = CurrencyConverter(
            fallback_on_missing_rate=True,
            fallback_on_wrong_date=True,
        )

    def calculate(self, portfolio: Dict[str, Iterable[Dict[str, object]]]) -> PortfolioResult:
        totals = Totals()
        positions: List[PositionBreakdown] = []
        for stock in portfolio.get("stocks", []):
            usd, twd, cost_usd, cost_twd, breakdown = self._value_stock(stock)
            totals.add(usd, twd, cost_usd, cost_twd)
            positions.append(breakdown)

        for cash in portfolio.get("cash", []):
            usd, twd, cost_usd, cost_twd, breakdown = self._value_cash(cash)
            totals.add(usd, twd, cost_usd, cost_twd)
            positions.append(breakdown)

        total_value_usd = totals.usd or 1.0  # avoid divide-by-zero
        for pos in positions:
            pos.portfolio_pct = (pos.value_usd / total_value_usd) * 100.0

        return PortfolioResult(totals=totals, positions=positions)

    def _value_stock(self, stock: Dict[str, object]) -> Tuple[float, float, float, float, PositionBreakdown]:
        symbol = str(stock["symbol"])
        shares = float(stock["shares"])
        average_cost = float(stock.get("average_cost", 0.0))
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

    def _value_cash(self, cash: Dict[str, object]) -> Tuple[float, float, float, float, PositionBreakdown]:
        currency = str(cash["currency"]).upper()
        amount = float(cash["amount"])
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
