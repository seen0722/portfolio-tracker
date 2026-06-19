"""Multi-horizon performance heatmap — close + % change of each asset over
several time windows (1D/1W/1M/3M/YTD), arranged to mirror a market-monitor
dashboard. `compute_changes` is pure and tested; the row list/order follows the
user's reference layout. FRED-sourced rows appear only when a FRED key is set.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

import pandas as pd

# (key, trading-days lookback) — QTD and YTD are handled specially.
_WINDOWS = [("1d", 1), ("1w", 5), ("1m", 21), ("3m", 63), ("1y", 252)]

# Display labels for the columns (key -> label), in order — matches the reference.
HORIZONS = [
    ("1d", "1天"), ("1w", "1週"), ("1m", "1月"), ("3m", "3月"),
    ("1y", "1年"), ("qtd", "QTD"), ("ytd", "YTD"),
]


def compute_changes(series: pd.Series, today: date) -> Dict[str, Optional[float]]:
    """% change over each window, plus QTD and YTD (None when not enough data)."""
    s = series.dropna().astype(float)
    if len(s) < 2:
        return {}
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_localize(None)
    latest = s.iloc[-1]
    out: Dict[str, Optional[float]] = {}
    for key, lookback in _WINDOWS:
        if len(s) > lookback:
            prev = s.iloc[-(lookback + 1)]
            out[key] = round((latest / prev - 1) * 100, 2) if prev else None

    quarter_start = pd.Timestamp(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
    qtd = s[s.index >= quarter_start]
    if len(qtd) >= 1 and qtd.iloc[0]:
        out["qtd"] = round((latest / qtd.iloc[0] - 1) * 100, 2)

    ytd = s[s.index.year == today.year]
    if len(ytd) >= 1 and ytd.iloc[0]:
        out["ytd"] = round((latest / ytd.iloc[0] - 1) * 100, 2)
    return out


class PerformanceHeatmap:
    # Ordered to mirror the reference dashboard. kind: "yf" (Yahoo) or "fred".
    ROWS = [
        ("利率・指數・商品", "美元 DXY", "yf", "DX-Y.NYB"),
        ("利率・指數・商品", "2年美債殖利率", "fred", "DGS2"),
        ("利率・指數・商品", "10年美債殖利率", "yf", "^TNX"),
        ("利率・指數・商品", "TLT 長天期美債", "yf", "TLT"),
        ("利率・指數・商品", "高收益債利差", "fred", "BAMLH0A0HYM2"),
        ("利率・指數・商品", "標普500", "yf", "^GSPC"),
        ("利率・指數・商品", "納指", "yf", "^IXIC"),
        ("利率・指數・商品", "道指", "yf", "^DJI"),
        ("利率・指數・商品", "黃金", "yf", "GC=F"),
        ("利率・指數・商品", "WTI 原油", "yf", "CL=F"),
        ("利率・指數・商品", "VIX 波動率", "yf", "^VIX"),
        ("利率・指數・商品", "軟體 IGV", "yf", "IGV"),
        ("利率・指數・商品", "羅素2000", "yf", "^RUT"),
        ("利率・指數・商品", "比特幣", "yf", "BTC-USD"),
        ("類股・風格", "通訊 XLC", "yf", "XLC"),
        ("類股・風格", "非必需消費 XLY", "yf", "XLY"),
        ("類股・風格", "必需消費 XLP", "yf", "XLP"),
        ("類股・風格", "能源 XLE", "yf", "XLE"),
        ("類股・風格", "銀行 KBWB", "yf", "KBWB"),
        ("類股・風格", "公用事業 XLU", "yf", "XLU"),
        ("類股・風格", "REITs IYR", "yf", "IYR"),
        ("類股・風格", "科技 XLK", "yf", "XLK"),
        ("類股・風格", "醫療 XLV", "yf", "XLV"),
        ("類股・風格", "國防 ITA", "yf", "ITA"),
        ("類股・風格", "保險 IAK", "yf", "IAK"),
        ("類股・風格", "半導體 SOXX", "yf", "SOXX"),
        ("類股・風格", "羅素1000價值 IWD", "yf", "IWD"),
        ("類股・風格", "羅素1000成長 IWF", "yf", "IWF"),
        ("類股・風格", "前七大科技 MAGS", "yf", "MAGS"),
        ("類股・風格", "標普等權重 RSP", "yf", "RSP"),
    ]

    def __init__(self, history_provider, fred_client=None) -> None:
        self.history_provider = history_provider
        self.fred_client = fred_client

    def build(self, holdings: Optional[List[str]] = None, period: str = "2y") -> List[Dict]:
        today = date.today()
        plan = list(self.ROWS) + [("我的持股", sym, "yf", sym) for sym in (holdings or [])]

        yf_tickers = sorted({tid for _, _, kind, tid in plan if kind == "yf"})
        closes = self.history_provider.get_closes(yf_tickers, period)
        columns = list(getattr(closes, "columns", []))
        fred_on = self.fred_client is not None and getattr(self.fred_client, "enabled", False)

        groups: Dict[str, List[Dict]] = {}
        for group, label, kind, tid in plan:
            if kind == "fred":
                if not fred_on:
                    continue  # hide FRED rows until a key is configured
                series = self.fred_client.history(tid, observation_days=500)
                series = series.dropna() if series is not None else None
            else:
                series = closes[tid].dropna().astype(float) if tid in columns else None

            row: Dict = {"label": label, "close": None, "changes": {}}
            if series is not None and not series.empty:
                close = float(series.iloc[-1])
                if tid == "^TNX" and close > 15:  # ^TNX is sometimes quoted x10
                    close /= 10.0
                row["close"] = round(close, 2)
                row["changes"] = compute_changes(series, today)
            groups.setdefault(group, []).append(row)

        return [{"name": name, "rows": rows} for name, rows in groups.items()]
