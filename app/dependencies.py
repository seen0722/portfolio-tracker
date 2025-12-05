"""Dependency container."""

import os
from pathlib import Path

from app.infrastructure.market_data import PriceFetcher
from app.infrastructure.persistence import HistoryRepository, PortfolioRepository
from app.services.portfolio_service import PortfolioService
from app.services.analysis_service import AnalysisService

# Configuration
PORTFOLIO_FILE = Path(os.environ.get("PORTFOLIO_FILE", "portfolio.json"))
PRICE_OVERRIDES_FILE = Path(os.environ.get("PRICE_OVERRIDES_FILE", "price_overrides.json"))
HISTORY_FILE = Path(os.environ.get("HISTORY_FILE", "history.csv"))
OVERRIDES_ONLY = os.environ.get("OVERRIDES_ONLY", "false").lower() == "true"

# Singletons
price_fetcher = PriceFetcher(
    overrides_path=PRICE_OVERRIDES_FILE,
    allow_online=not OVERRIDES_ONLY,
)

portfolio_service = PortfolioService(price_fetcher)
analysis_service = AnalysisService(price_fetcher)
history_repository = HistoryRepository(HISTORY_FILE)
portfolio_repository = PortfolioRepository(PORTFOLIO_FILE)
