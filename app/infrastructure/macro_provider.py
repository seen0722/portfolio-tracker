"""Macro data provider — market-priced factors via yfinance, macro-economic
series via FRED (BYO key). Degrades gracefully: factors whose source is
unavailable simply come back UNKNOWN, mirroring the LLM/Telegram fallbacks.
"""

from __future__ import annotations

import concurrent.futures
import logging
from datetime import date
from typing import List, Optional, Tuple

import yfinance as yf

from app.domain.macro import MacroIndicator, MarketRegime
from app.services.market_regime import SPECS, build_indicator, compute_regime

logger = logging.getLogger(__name__)

# Market-priced factors (Yahoo). US10Y from ^TNX may come scaled x10.
_YF_TICKERS = {
    "VIX": "^VIX",
    "US10Y": "^TNX",
    "DXY": "DX-Y.NYB",
    "SOX": "^SOX",
    "GOLD": "GC=F",
    "WTI": "CL=F",
}
# Macro-economic series (FRED).
_FRED_SERIES = {
    "HYOAS": "BAMLH0A0HYM2",  # ICE BofA US High Yield OAS (%)
    "T10Y2Y": "T10Y2Y",  # 10Y - 2Y spread (%)
    "REAL10Y": "DFII10",  # 10Y TIPS real yield (%)
}
_FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


class FredClient:
    """Minimal FRED observations client (latest value + a ~1-week-ago reference)."""

    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def fetch(self, series_id: str) -> Tuple[Optional[float], Optional[float], str]:
        today = date.today().isoformat()
        if not self.api_key:
            return None, None, today
        import requests

        try:
            resp = requests.get(
                _FRED_URL,
                params={
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": "12",
                },
                timeout=15,
            )
            resp.raise_for_status()
            obs = resp.json().get("observations", [])
            points = [(o["date"], float(o["value"])) for o in obs if o.get("value") not in (".", "", None)]
            if not points:
                return None, None, today
            latest = points[0]
            ref = points[5] if len(points) > 5 else points[-1]
            return latest[1], ref[1], latest[0]
        except Exception as exc:  # degrade to UNKNOWN
            logger.warning("FRED fetch failed for %s: %s", series_id, exc)
            return None, None, today

    def history(self, series_id: str, observation_days: int = 220):
        """Return a date-indexed pandas Series of recent observations (or None)."""
        if not self.api_key:
            return None
        import pandas as pd
        import requests
        from datetime import date, timedelta

        try:
            start = (date.today() - timedelta(days=observation_days)).isoformat()
            resp = requests.get(
                _FRED_URL,
                params={
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "observation_start": start,
                    "sort_order": "asc",
                },
                timeout=20,
            )
            resp.raise_for_status()
            obs = resp.json().get("observations", [])
            points = [(o["date"], float(o["value"])) for o in obs if o.get("value") not in (".", "", None)]
            if not points:
                return None
            return pd.Series([p[1] for p in points], index=pd.to_datetime([p[0] for p in points]))
        except Exception as exc:
            logger.warning("FRED history failed for %s: %s", series_id, exc)
            return None


class MacroProvider:
    def __init__(self, allow_online: bool = True, fred_api_key: Optional[str] = None) -> None:
        self.allow_online = allow_online
        self.fred = FredClient(fred_api_key)

    def indicators(self) -> List[MacroIndicator]:
        keys = list(SPECS.keys())
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_key = {executor.submit(self._fetch_one, key): key for key in keys}
            results = {}
            for future in concurrent.futures.as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    results[key] = future.result()
                except Exception as exc:
                    logger.warning("Macro fetch failed for %s: %s", key, exc)
                    results[key] = build_indicator(key, None, None, date.today().isoformat())
        # Preserve the SPECS order for stable UI rendering.
        return [results[key] for key in keys]

    def regime(self) -> MarketRegime:
        indicators = self.indicators()
        as_of = max((i.as_of for i in indicators), default=date.today().isoformat())
        return compute_regime(indicators, as_of)

    def _fetch_one(self, key: str) -> MacroIndicator:
        today = date.today().isoformat()
        if not self.allow_online:
            return build_indicator(key, None, None, today)
        if key in _YF_TICKERS:
            value, ref, as_of = self._fetch_yf(_YF_TICKERS[key], normalize=(key == "US10Y"))
        elif key in _FRED_SERIES:
            value, ref, as_of = self.fred.fetch(_FRED_SERIES[key])
        else:
            value, ref, as_of = None, None, today
        return build_indicator(key, value, ref, as_of)

    @staticmethod
    def _fetch_yf(ticker: str, normalize: bool = False) -> Tuple[Optional[float], Optional[float], str]:
        today = date.today().isoformat()
        try:
            hist = yf.Ticker(ticker).history(period="1mo")
            if hist is None or hist.empty or "Close" not in hist:
                return None, None, today
            closes = [float(c) for c in hist["Close"].dropna().tolist()]
            if not closes:
                return None, None, today
            value = closes[-1]
            ref = closes[-6] if len(closes) >= 6 else closes[0]
            if normalize and value > 15:  # ^TNX sometimes quoted x10
                value, ref = value / 10.0, ref / 10.0
            as_of = str(hist.index[-1])[:10]
            return value, ref, as_of
        except Exception as exc:
            logger.warning("Yahoo macro fetch failed for %s: %s", ticker, exc)
            return None, None, today
