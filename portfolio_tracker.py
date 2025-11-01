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

    def add(self, usd: float, twd: float) -> None:
        self.usd += usd
        self.twd += twd


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
            usd, twd, breakdown = self._value_stock(stock)
            totals.add(usd, twd)
            positions.append(breakdown)

        for cash in portfolio.get("cash", []):
            usd, twd, breakdown = self._value_cash(cash)
            totals.add(usd, twd)
            positions.append(breakdown)

        total_value_usd = totals.usd or 1.0  # avoid divide-by-zero
        for pos in positions:
            pos.portfolio_pct = (pos.value_usd / total_value_usd) * 100.0

        return PortfolioResult(totals=totals, positions=positions)

    def _value_stock(self, stock: Dict[str, object]) -> Tuple[float, float, PositionBreakdown]:
        symbol = str(stock["symbol"])
        shares = float(stock["shares"])
        price = self.price_fetcher.get_price(symbol)

        price_currency = "TWD" if ".TW" in symbol.upper() else "USD"
        if ".TW" in symbol.upper():
            value_twd = price * shares
            value_usd = self._convert(value_twd, "TWD", "USD")
        else:
            value_usd = price * shares
            value_twd = self._convert(value_usd, "USD", "TWD")

        breakdown = PositionBreakdown(
            name=symbol,
            category="stock",
            value_usd=value_usd,
            value_twd=value_twd,
            portfolio_pct=0.0,
            quantity=shares,
            unit_price=price,
            price_currency=price_currency,
        )
        return value_usd, value_twd, breakdown

    def _value_cash(self, cash: Dict[str, object]) -> Tuple[float, float, PositionBreakdown]:
        currency = str(cash["currency"]).upper()
        amount = float(cash["amount"])
        value_usd = self._convert(amount, currency, "USD")
        value_twd = self._convert(amount, currency, "TWD")
        breakdown = PositionBreakdown(
            name=currency,
            category="cash",
            value_usd=value_usd,
            value_twd=value_twd,
            portfolio_pct=0.0,
            quantity=amount,
            unit_price=None,
            price_currency=currency,
        )
        return value_usd, value_twd, breakdown

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
