"""Persistence helpers for portfolio data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

import pandas as pd

from app.domain.models import Portfolio, Stock, Cash

CSV_COLUMNS = ["date", "total_usd", "total_twd", "daily_return_pct"]


class HistoryRepository:
    """Read and write portfolio history to a CSV file."""

    def __init__(self, path: Path = Path("history.csv")) -> None:
        self.path = path

    def load(self) -> pd.DataFrame:
        if self.path.exists():
            df = pd.read_csv(self.path)
            if not df.empty and "date" in df.columns:
                df.sort_values("date", inplace=True)
            return df
        return pd.DataFrame(columns=CSV_COLUMNS)

    def save(self, df: pd.DataFrame) -> None:
        df.to_csv(self.path, index=False)

    def upsert(
        self, record_date: str, total_usd: float, total_twd: float
    ) -> pd.DataFrame:
        df = self.load()
        new_row = {
            "date": record_date,
            "total_usd": round(total_usd, 2),
            "total_twd": round(total_twd, 2),
            "daily_return_pct": 0.0,
        }

        if record_date in df["date"].values:
            df.loc[df["date"] == record_date, ["total_usd", "total_twd"]] = [
                new_row["total_usd"],
                new_row["total_twd"],
            ]
        else:
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        df = self._recalculate_returns(df)
        self.save(df)
        return df

    @staticmethod
    def _recalculate_returns(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df.sort_values("date", inplace=True)
        df["daily_return_pct"] = df["total_usd"].pct_change().fillna(0.0) * 100.0
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")
        return df


class PortfolioRepository:
    """Read and write portfolio data to a JSON file."""

    def __init__(self, path: Path = Path("portfolio.json")) -> None:
        self.path = path

    def load(self) -> Portfolio:
        if not self.path.exists():
            raise FileNotFoundError(f"Portfolio file not found: {self.path}")
        
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            
        stocks = [
            Stock(
                symbol=s["symbol"],
                shares=float(s["shares"]),
                average_cost=float(s.get("average_cost", 0.0))
            )
            for s in data.get("stocks", [])
        ]
        
        cash = [
            Cash(
                currency=c["currency"],
                amount=float(c["amount"])
            )
            for c in data.get("cash", [])
        ]
        
        return Portfolio(stocks=stocks, cash=cash)

    def save(self, portfolio: Portfolio) -> None:
        data: Dict[str, List[Dict[str, Any]]] = {
            "stocks": [
                {
                    "symbol": s.symbol,
                    "shares": s.shares,
                    "average_cost": s.average_cost
                }
                for s in portfolio.stocks
            ],
            "cash": [
                {
                    "currency": c.currency,
                    "amount": c.amount
                }
                for c in portfolio.cash
            ]
        }
        
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
