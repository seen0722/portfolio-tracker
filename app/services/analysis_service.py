"""Service for advanced financial analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional

import pandas as pd
import numpy as np

from app.domain.models import Portfolio, Stock
from app.infrastructure.market_data import PriceFetcher

logger = logging.getLogger(__name__)

@dataclass
class PortfolioAnalysis:
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    beta: float
    alpha: float

class AnalysisService:
    """Calculates professional financial metrics for the portfolio."""

    def __init__(self, price_fetcher: PriceFetcher, risk_free_rate: float = 0.02) -> None:
        self.price_fetcher = price_fetcher
        self.risk_free_rate = risk_free_rate

    def analyze(self, portfolio: Portfolio) -> PortfolioAnalysis:
        """
        Calculate advanced metrics for the entire portfolio.
        
        Note: This is a simplified implementation. A real professional tool would:
        1. Fetch historical prices for ALL assets in the portfolio.
        2. Calculate daily weighted returns of the portfolio.
        3. Compare against a benchmark (e.g., SPY).
        """
        # For now, we will simulate some of this based on the 'history.csv' data 
        # if we had access to it here, or we can fetch historical data for major positions.
        
        # Let's try to fetch history for the largest position to give a "proxy" analysis
        # or just return placeholders if we can't do full analysis yet.
        
        # To do this properly, we need the PortfolioResult history (daily totals).
        # But here we only have the current Portfolio state.
        # We should probably accept a history dataframe as input or fetch it.
        
        return PortfolioAnalysis(
            volatility=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            beta=0.0,
            alpha=0.0
        )

    def analyze_history(self, history_df: pd.DataFrame) -> PortfolioAnalysis:
        """
        Calculate metrics based on the portfolio's historical total value.
        This treats the portfolio as a single fund.
        """
        if history_df.empty or len(history_df) < 2:
            return PortfolioAnalysis(0, 0, 0, 0, 0)

        # Ensure sorted by date
        df = history_df.sort_values("date").copy()
        
        # Calculate daily returns if not present (though they should be)
        if "daily_return_pct" not in df.columns:
            df["daily_return_pct"] = df["total_usd"].pct_change().fillna(0.0) * 100.0
            
        returns = df["daily_return_pct"] / 100.0
        
        # 1. Volatility (Annualized standard deviation)
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(252)
        
        # 2. Sharpe Ratio (assuming 0% risk free for simplicity or use self.risk_free_rate)
        # Annualized Excess Return / Annualized Volatility
        avg_daily_ret = returns.mean()
        annual_ret = avg_daily_ret * 252
        sharpe = (annual_ret - self.risk_free_rate) / annual_vol if annual_vol != 0 else 0.0
        
        # 3. Max Drawdown
        # Calculate cumulative returns (wealth index)
        wealth_index = (1 + returns).cumprod()
        previous_peaks = wealth_index.cummax()
        drawdowns = (wealth_index - previous_peaks) / previous_peaks
        max_drawdown = drawdowns.min()
        
        # 4. Beta & Alpha (Requires Benchmark)
        # For now, we'll default these to 1.0 and 0.0 as we don't have benchmark data loaded yet.
        beta = 1.0
        alpha = 0.0
        
        return PortfolioAnalysis(
            volatility=round(annual_vol * 100, 2), # as percentage
            sharpe_ratio=round(sharpe, 2),
            max_drawdown=round(max_drawdown * 100, 2), # as percentage
            beta=beta,
            alpha=alpha
        )
