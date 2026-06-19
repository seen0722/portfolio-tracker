"""AI capex monitor: fetches hyperscaler / chip-maker capital expenditure and
derives a leading signal from its *rate of change* (the second derivative).

Rationale: a "shovel maker" (NVDA/TSM/MU) does not get hurt when capex *falls*;
it gets hurt when capex *growth decelerates* versus what the market priced in.
So the signal here keys off year-over-year growth and whether it is accelerating
or decelerating, not the absolute capex level.
"""

from __future__ import annotations

import concurrent.futures
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import yfinance as yf

logger = logging.getLogger(__name__)

# Default watch-lists.
#
# DEMAND side: hyperscaler capex *is* the suppliers' revenue. This is the core
# signal — when this growth decelerates, the whole "shovel" trade is at risk.
DEMAND_SIDE: Tuple[str, ...] = ("AMZN", "GOOGL", "MSFT", "META", "ORCL")
# SUPPLY side: heavy-capex foundry / memory. Their capex = future *supply*
# (over-capacity risk, especially for memory). Conceptually distinct from demand.
SUPPLY_SIDE: Tuple[str, ...] = ("TSM", "MU")
# NOTE: fabless names (NVDA, AVGO, AMD) are deliberately excluded — they don't
# build fabs, so their own capex is tiny and is NOT a demand signal. Track them
# by revenue instead. Query them explicitly via ?symbols= if needed.

# Number of quarters back that constitutes "a year ago" (4 fiscal quarters).
YOY_LAG = 4
# Minimum change in YoY growth (in percentage points) to call a trend
# accelerating/decelerating rather than stable. Filters out noise.
GROWTH_EPS_PP = 0.5

# Capital-expenditure line label as exposed by yfinance cash-flow statements.
_CAPEX_LABEL = "Capital Expenditure"


@dataclass(frozen=True)
class CapexQuarter:
    """A single reported quarter of capital expenditure.

    `capex` is stored as a positive magnitude in absolute currency (USD),
    even though cash-flow statements report it as a negative outflow.
    """

    period: str  # ISO date string, e.g. "2026-03-31"
    capex: float


@dataclass(frozen=True)
class CapexSignal:
    """Derived capex signal for one symbol.

    `light` is the headline traffic light:
      green   -> growth accelerating or stable
      yellow  -> growth decelerated for one quarter
      red     -> growth decelerated two quarters in a row, or YoY turned negative
      unknown -> insufficient data
    """

    symbol: str
    latest_period: Optional[str]
    latest_capex: Optional[float]
    yoy_growth_pct: Optional[float]
    qoq_growth_pct: Optional[float]
    yoy_prev_growth_pct: Optional[float]
    trend: str
    light: str
    next_earnings: Optional[str]
    currency: Optional[str] = None
    note: str = ""


def _growth_pct(curr: Optional[float], prior: Optional[float]) -> Optional[float]:
    """Percentage growth from `prior` to `curr`; None when not computable."""
    if curr is None or prior is None or prior == 0:
        return None
    return (curr - prior) / prior * 100.0


def _yoy_at(quarters: List[CapexQuarter], idx: int) -> Optional[float]:
    """Year-over-year growth for the quarter at `idx` (quarters newest-first)."""
    lagged = idx + YOY_LAG
    if idx < 0 or lagged >= len(quarters):
        return None
    return _growth_pct(quarters[idx].capex, quarters[lagged].capex)


def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 1)


def _classify(
    y0: Optional[float], y1: Optional[float], y2: Optional[float]
) -> Tuple[str, str, str]:
    """Map the last three YoY growth readings to (trend, light, note)."""
    if y0 is None:
        return "unknown", "unknown", "YoY 資料不足"
    if y0 < 0:
        return "decelerating", "red", "capex YoY 轉負，鏟子需求收縮"
    if y1 is None:
        return "unknown", "unknown", "僅一個 YoY 點，無法判斷趨勢"
    if y0 > y1 + GROWTH_EPS_PP:
        return "accelerating", "green", "capex 成長加速"
    if y0 < y1 - GROWTH_EPS_PP:
        if y2 is not None and y1 < y2 - GROWTH_EPS_PP:
            return "decelerating", "red", "capex 成長連兩季減速"
        return "decelerating", "yellow", "capex 成長單季減速，留意"
    return "stable", "green", "capex 成長維持"


def compute_capex_signal(
    symbol: str,
    quarters: List[CapexQuarter],
    next_earnings: Optional[str] = None,
    currency: Optional[str] = None,
) -> CapexSignal:
    """Pure transform from reported quarters to a CapexSignal.

    Network-free and deterministic, so it carries the unit-test weight.
    """
    ordered = sorted(quarters, key=lambda q: q.period, reverse=True)
    if not ordered:
        return CapexSignal(
            symbol=symbol,
            latest_period=None,
            latest_capex=None,
            yoy_growth_pct=None,
            qoq_growth_pct=None,
            yoy_prev_growth_pct=None,
            trend="unknown",
            light="unknown",
            next_earnings=next_earnings,
            currency=currency,
            note="無 capex 資料",
        )

    latest = ordered[0]
    qoq = _growth_pct(ordered[0].capex, ordered[1].capex) if len(ordered) >= 2 else None
    y0 = _yoy_at(ordered, 0)
    y1 = _yoy_at(ordered, 1)
    y2 = _yoy_at(ordered, 2)
    trend, light, note = _classify(y0, y1, y2)

    return CapexSignal(
        symbol=symbol,
        latest_period=latest.period,
        latest_capex=latest.capex,
        yoy_growth_pct=_round(y0),
        qoq_growth_pct=_round(qoq),
        yoy_prev_growth_pct=_round(y1),
        trend=trend,
        light=light,
        next_earnings=next_earnings,
        currency=currency,
        note=note,
    )


@dataclass
class CapexMonitor:
    """Fetch quarterly capex + next earnings date via yfinance and derive signals."""

    allow_online: bool = True
    cache_ttl_seconds: int = 6 * 60 * 60  # capex is quarterly; cache aggressively
    _cache: Dict[str, Tuple[CapexSignal, float]] = field(default_factory=dict, init=False)

    def get_signal(self, symbol: str) -> CapexSignal:
        """Return the capex signal for one symbol, using the cache when fresh."""
        cached = self._cache.get(symbol)
        if cached is not None and time.time() - cached[1] < self.cache_ttl_seconds:
            logger.debug("Using cached capex signal for %s", symbol)
            return cached[0]

        if not self.allow_online:
            return compute_capex_signal(symbol, [], None)

        quarters, next_earnings, currency = self._fetch(symbol)
        signal = compute_capex_signal(symbol, quarters, next_earnings, currency)
        self._cache[symbol] = (signal, time.time())
        return signal

    def get_signals(self, symbols: List[str]) -> Dict[str, CapexSignal]:
        """Fetch signals for several symbols in parallel."""
        results: Dict[str, CapexSignal] = {}
        to_fetch: List[str] = []

        for symbol in symbols:
            cached = self._cache.get(symbol)
            if cached is not None and time.time() - cached[1] < self.cache_ttl_seconds:
                results[symbol] = cached[0]
            else:
                to_fetch.append(symbol)

        if not to_fetch:
            return results

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_symbol = {
                executor.submit(self.get_signal, symbol): symbol for symbol in to_fetch
            }
            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    results[symbol] = future.result()
                except Exception as exc:  # degrade gracefully, never crash the page
                    logger.error("Error building capex signal for %s: %s", symbol, exc)
                    results[symbol] = compute_capex_signal(symbol, [], None)

        return results

    def _fetch(
        self, symbol: str
    ) -> Tuple[List[CapexQuarter], Optional[str], Optional[str]]:
        """Pull raw quarterly capex, next earnings date, and reporting currency.

        This is the single network seam; unit tests monkeypatch it.
        """
        try:
            ticker = yf.Ticker(symbol)
            quarters = self._parse_capex(ticker)
            next_earnings = self._parse_next_earnings(ticker)
            currency = self._parse_currency(ticker)
            return quarters, next_earnings, currency
        except Exception as exc:
            logger.warning("Failed to fetch capex for %s: %s", symbol, exc)
            return [], None, None

    @staticmethod
    def _parse_capex(ticker: "yf.Ticker") -> List[CapexQuarter]:
        cashflow = ticker.quarterly_cashflow
        if cashflow is None or cashflow.empty:
            return []
        rows = [idx for idx in cashflow.index if _CAPEX_LABEL in str(idx)]
        if not rows:
            return []
        series = cashflow.loc[rows[0]].dropna()
        quarters: List[CapexQuarter] = []
        for period, value in series.items():
            try:
                quarters.append(
                    CapexQuarter(period=str(period)[:10], capex=abs(float(value)))
                )
            except (TypeError, ValueError):
                continue
        quarters.sort(key=lambda q: q.period, reverse=True)
        return quarters

    @staticmethod
    def _parse_next_earnings(ticker: "yf.Ticker") -> Optional[str]:
        calendar = ticker.calendar
        if not isinstance(calendar, dict):
            return None
        dates = calendar.get("Earnings Date")
        if not dates:
            return None
        first = dates[0]
        return first.isoformat() if hasattr(first, "isoformat") else str(first)

    @staticmethod
    def _parse_currency(ticker: "yf.Ticker") -> Optional[str]:
        """Reporting currency of the financial statements (e.g. USD, TWD)."""
        try:
            info = ticker.get_info()
        except Exception:
            return None
        if not isinstance(info, dict):
            return None
        return info.get("financialCurrency")
