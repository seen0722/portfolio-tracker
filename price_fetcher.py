"""Price fetching utilities with multiple data sources."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Dict, Optional, Set

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

STOOQ_URL = "https://stooq.com/q/d/l/"


class PriceFetchError(RuntimeError):
    """Raised when no price source can provide data."""


@dataclass
class PriceFetcher:
    """Fetch instrument prices using Yahoo Finance, Stooq, or local overrides."""

    overrides_path: Path = Path("price_overrides.json")
    allow_online: bool = True
    _overrides: Dict[str, float] = field(default_factory=dict, init=False)
    online_sources_used: Set[str] = field(default_factory=set, init=False)
    overrides_used: Set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        self._load_overrides()

    def _load_overrides(self) -> None:
        if not self.overrides_path.exists():
            logger.debug("No local override file found at %s", self.overrides_path)
            self._overrides = {}
            return
        try:
            with self.overrides_path.open("r", encoding="utf-8") as handle:
                overrides = json.load(handle)
            self._overrides = {
                str(symbol): float(value) for symbol, value in overrides.items()
            }
            logger.info(
                "Loaded %d local price overrides from %s",
                len(self._overrides),
                self.overrides_path,
            )
        except Exception as exc:
            logger.warning("Failed to load local overrides: %s", exc)
            self._overrides = {}

    def refresh_overrides(self) -> None:
        """Reload the overrides from disk."""
        self._load_overrides()

    def get_price(self, symbol: str) -> float:
        """Retrieve the latest close price for the symbol."""
        if self.allow_online:
            price = self._fetch_yahoo(symbol)
            if price is not None:
                self.online_sources_used.add("Yahoo Finance")
                logger.info("Using Yahoo Finance price for %s: %.4f", symbol, price)
                return price

            price = self._fetch_stooq(symbol)
            if price is not None:
                self.online_sources_used.add("Stooq")
                logger.info("Using Stooq price for %s: %.4f", symbol, price)
                return price

        price = self._overrides.get(symbol)
        if price is not None:
            self.overrides_used.add(symbol)
            logger.info("Using local override price for %s: %.4f", symbol, price)
            return price

        raise PriceFetchError(
            f"No price data available for {symbol} "
            f"(online allowed={self.allow_online}, overrides found={bool(self._overrides)})"
        )

    @staticmethod
    def _fetch_yahoo(symbol: str) -> Optional[float]:
        """Fetch price via Yahoo Finance."""
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(period="1d")
            if history.empty or "Close" not in history:
                logger.debug("Yahoo Finance returned empty history for %s", symbol)
                return None
            return float(history["Close"].iloc[-1])
        except Exception as exc:
            logger.debug("Yahoo Finance fetch failed for %s: %s", symbol, exc)
            return None

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Convert ticker symbol to Stooq format."""
        if "." in symbol:
            return symbol
        return f"{symbol}.US"

    @classmethod
    def _fetch_stooq(cls, symbol: str) -> Optional[float]:
        """Fetch price via Stooq daily CSV data."""
        stooq_symbol = cls._normalize_symbol(symbol)
        params = {"s": stooq_symbol, "i": "d"}
        try:
            response = requests.get(STOOQ_URL, params=params, timeout=10)
            response.raise_for_status()
            df = pd.read_csv(StringIO(response.text))
        except Exception as exc:
            logger.debug("Stooq fetch failed for %s: %s", symbol, exc)
            return None

        if df.empty or "Close" not in df:
            logger.debug("Stooq returned empty data for %s", symbol)
            return None

        df["Date"] = pd.to_datetime(df["Date"])
        df.sort_values("Date", inplace=True)
        return float(df["Close"].iloc[-1])

    def describe_sources(self) -> str:
        """Human readable description of data sources used."""
        parts: list[str] = []
        if self.online_sources_used:
            parts.append(
                "Online sources: " + ", ".join(sorted(self.online_sources_used))
            )
        if self.overrides_used:
            parts.append(
                "Overrides applied for: "
                + ", ".join(sorted(self.overrides_used))
            )
        if not parts:
            parts.append("No price sources were used.")
        return " | ".join(parts)
