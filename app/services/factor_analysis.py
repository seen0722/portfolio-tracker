"""Factor analysis — correlate a target (portfolio NAV or a single holding)
against the macro factors over time, and produce a normalized overlay series.

`compute_sensitivity` and `overlay_series` are pure (operate on pandas Series),
so they carry the test weight. FactorAnalysisService wires them to the NAV
history, yfinance factor history, and FRED history.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd


def _norm(series: pd.Series) -> pd.Series:
    """Normalize a series' index to naive, de-duplicated, sorted daily dates."""
    s = series.dropna().astype(float)
    idx = pd.to_datetime(s.index)
    try:
        idx = idx.tz_localize(None)
    except (TypeError, AttributeError):
        try:
            idx = idx.tz_convert(None)
        except Exception:
            pass
    s.index = idx.normalize()
    return s[~s.index.duplicated(keep="last")].sort_index()


def compute_sensitivity(
    target: pd.Series, factors: Dict[str, pd.Series], min_points: int = 10
) -> List[Dict]:
    """Correlation of target daily returns vs each factor's daily change.

    Returned rows are sorted by |corr| descending (uncomputable ones last).
    """
    tr = _norm(target).pct_change()
    rows: List[Dict] = []
    for key, factor in factors.items():
        joined = pd.concat([tr, _norm(factor).pct_change()], axis=1, join="inner").dropna()
        if len(joined) < min_points:
            rows.append({"key": key, "corr": None, "n": int(len(joined))})
            continue
        corr = joined.iloc[:, 0].corr(joined.iloc[:, 1])
        rows.append(
            {"key": key, "corr": (round(float(corr), 3) if pd.notna(corr) else None), "n": int(len(joined))}
        )
    rows.sort(key=lambda r: (r["corr"] is None, -abs(r["corr"]) if r["corr"] is not None else 0.0))
    return rows


def overlay_series(target: pd.Series, factor: pd.Series) -> Dict:
    """Both series rebased to cumulative % change from the first common date."""
    joined = pd.concat([_norm(target), _norm(factor)], axis=1, join="inner").dropna()
    if joined.empty or joined.iloc[0, 0] == 0 or joined.iloc[0, 1] == 0:
        return {"dates": [], "target_pct": [], "factor_pct": []}
    target_pct = (joined.iloc[:, 0] / joined.iloc[0, 0] - 1.0) * 100.0
    factor_pct = (joined.iloc[:, 1] / joined.iloc[0, 1] - 1.0) * 100.0
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in joined.index],
        "target_pct": [round(float(x), 2) for x in target_pct],
        "factor_pct": [round(float(x), 2) for x in factor_pct],
    }


class FactorAnalysisService:
    _YF = {"VIX": "^VIX", "US10Y": "^TNX", "DXY": "DX-Y.NYB", "SOX": "^SOX", "GOLD": "GC=F", "WTI": "CL=F"}
    _FRED = {"HYOAS": "BAMLH0A0HYM2", "T10Y2Y": "T10Y2Y", "REAL10Y": "DFII10"}

    def __init__(self, nav_service, history_provider, fred_client=None) -> None:
        self.nav_service = nav_service
        self.history_provider = history_provider
        self.fred_client = fred_client

    def factor_histories(self, period: str = "6mo") -> Dict[str, pd.Series]:
        out: Dict[str, pd.Series] = {}
        closes = self.history_provider.get_closes(list(self._YF.values()), period)
        columns = list(getattr(closes, "columns", []))
        for key, ticker in self._YF.items():
            if ticker in columns:
                series = closes[ticker].dropna().astype(float)
                if key == "US10Y":
                    series = series.apply(lambda x: x / 10.0 if x > 15 else x)
                out[key] = series
        if self.fred_client is not None and getattr(self.fred_client, "enabled", False):
            for key, series_id in self._FRED.items():
                series = self.fred_client.history(series_id)
                if series is not None and len(series) > 5:
                    out[key] = series
        return out

    def target_series(self, target: str, period: str = "6mo") -> pd.Series:
        if target == "portfolio":
            hist = self.nav_service.history()
            if hist is None or hist.empty:
                return pd.Series(dtype=float)
            return pd.Series(hist["total_usd"].astype(float).values, index=pd.to_datetime(hist["date"]))
        closes = self.history_provider.get_closes([target], period)
        if target in getattr(closes, "columns", []):
            return closes[target].dropna().astype(float)
        return pd.Series(dtype=float)

    def analyze(self, target: str = "portfolio", period: str = "6mo", factor: Optional[str] = None) -> Dict:
        from app.services.market_regime import SPECS

        tgt = self.target_series(target, period)
        factors = self.factor_histories(period)
        sensitivity = compute_sensitivity(tgt, factors)
        for row in sensitivity:
            row["label"] = SPECS.get(row["key"], {}).get("label", row["key"])

        chosen = factor if factor in factors else next(
            (r["key"] for r in sensitivity if r["corr"] is not None), None
        )
        overlay = overlay_series(tgt, factors[chosen]) if chosen in factors else {
            "dates": [], "target_pct": [], "factor_pct": []
        }
        return {
            "target": target,
            "period": period,
            "factor": chosen,
            "factor_label": SPECS.get(chosen, {}).get("label", chosen) if chosen else None,
            "sensitivity": sensitivity,
            "overlay": overlay,
        }
