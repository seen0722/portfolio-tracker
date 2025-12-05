from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Asset:
    """Base class for any asset."""
    pass

@dataclass
class Stock(Asset):
    symbol: str
    shares: float
    average_cost: float = 0.0

@dataclass
class Cash(Asset):
    currency: str
    amount: float

@dataclass
class Portfolio:
    stocks: List[Stock] = field(default_factory=list)
    cash: List[Cash] = field(default_factory=list)

@dataclass
class Totals:
    usd: float = 0.0
    twd: float = 0.0
    cost_usd: float = 0.0
    cost_twd: float = 0.0
    unrealized_pl_usd: float = 0.0
    unrealized_pl_twd: float = 0.0
    roi_pct: float = 0.0

    def add(self, usd: float, twd: float, cost_usd: float, cost_twd: float) -> None:
        self.usd += usd
        self.twd += twd
        self.cost_usd += cost_usd
        self.cost_twd += cost_twd
        self.unrealized_pl_usd = self.usd - self.cost_usd
        self.unrealized_pl_twd = self.twd - self.cost_twd
        self.roi_pct = (self.unrealized_pl_usd / self.cost_usd * 100.0) if self.cost_usd else 0.0

@dataclass
class PositionBreakdown:
    name: str
    category: str
    value_usd: float
    value_twd: float
    portfolio_pct: float
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    price_currency: Optional[str] = None
    average_cost: Optional[float] = None
    total_cost_usd: float = 0.0
    total_cost_twd: float = 0.0
    unrealized_pl_usd: float = 0.0
    unrealized_pl_twd: float = 0.0
    roi_pct: float = 0.0

@dataclass
class PortfolioResult:
    totals: Totals
    positions: List[PositionBreakdown]
