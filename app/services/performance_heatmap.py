"""Multi-horizon performance heatmap — % change of each asset over several
time windows (1D/1W/1M/3M/YTD), grouped by category. This is the scannable
"what's moving, how strongly, across timeframes" view (replaces the weak
two-line overlay). `compute_changes` is pure and tested.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

import pandas as pd

# (key, trading-days lookback) — YTD is handled specially.
_WINDOWS = [("1d", 1), ("1w", 5), ("1m", 21), ("3m", 63)]

# Display labels for the columns (key -> label), in order.
HORIZONS = [("1d", "1天"), ("1w", "1週"), ("1m", "1月"), ("3m", "3月"), ("ytd", "YTD")]


def compute_changes(series: pd.Series, year: int) -> Dict[str, Optional[float]]:
    """% change of `series` over each window and YTD (None when not enough data)."""
    s = series.dropna().astype(float)
    if len(s) < 2:
        return {}
    latest = s.iloc[-1]
    out: Dict[str, Optional[float]] = {}
    for key, lookback in _WINDOWS:
        if len(s) > lookback:
            prev = s.iloc[-(lookback + 1)]
            out[key] = round((latest / prev - 1) * 100, 2) if prev else None
    ytd = s[s.index.year == year]
    if len(ytd) >= 1 and ytd.iloc[0]:
        out["ytd"] = round((latest / ytd.iloc[0] - 1) * 100, 2)
    return out


class PerformanceHeatmap:
    _INDICES = [
        ("標普500", "^GSPC"), ("納指", "^IXIC"), ("道指", "^DJI"),
        ("羅素2000", "^RUT"), ("費半 SOX", "^SOX"),
    ]
    _SECTORS = [
        ("科技 XLK", "XLK"), ("通訊 XLC", "XLC"), ("非必需消費 XLY", "XLY"),
        ("必需消費 XLP", "XLP"), ("能源 XLE", "XLE"), ("金融 XLF", "XLF"),
        ("醫療 XLV", "XLV"), ("工業 XLI", "XLI"), ("原物料 XLB", "XLB"),
        ("公用 XLU", "XLU"), ("房地產 XLRE", "XLRE"),
    ]
    _FACTORS_YF = [
        ("VIX 波動率", "^VIX"), ("10Y 殖利率", "^TNX"), ("美元 DXY", "DX-Y.NYB"),
        ("黃金", "GC=F"), ("WTI 原油", "CL=F"),
    ]
    _FACTORS_FRED = [
        ("10Y 實質殖利率", "DFII10"), ("高收益利差", "BAMLH0A0HYM2"), ("2s10s 曲線", "T10Y2Y"),
    ]

    def __init__(self, history_provider, fred_client=None) -> None:
        self.history_provider = history_provider
        self.fred_client = fred_client

    def build(self, holdings: Optional[List[str]] = None, period: str = "1y") -> List[Dict]:
        year = date.today().year
        plan = (
            [("總體因子", label, t) for label, t in self._FACTORS_YF]
            + [("主要指數", label, t) for label, t in self._INDICES]
            + [("類股", label, t) for label, t in self._SECTORS]
            + [("我的持股", sym, sym) for sym in (holdings or [])]
        )
        tickers = sorted({row[2] for row in plan})
        closes = self.history_provider.get_closes(tickers, period)
        columns = list(getattr(closes, "columns", []))

        order = ["總體因子", "主要指數", "類股", "我的持股"]
        groups: Dict[str, List[Dict]] = {name: [] for name in order}
        for group, label, ticker in plan:
            changes: Dict = {}
            if ticker in columns:
                changes = compute_changes(closes[ticker].dropna().astype(float), year)
            groups[group].append({"label": label, "changes": changes})

        if self.fred_client is not None and getattr(self.fred_client, "enabled", False):
            for label, series_id in self._FACTORS_FRED:
                series = self.fred_client.history(series_id, observation_days=400)
                changes = compute_changes(series, year) if series is not None else {}
                groups["總體因子"].append({"label": label, "changes": changes})

        return [{"name": name, "rows": groups[name]} for name in order if groups[name]]
