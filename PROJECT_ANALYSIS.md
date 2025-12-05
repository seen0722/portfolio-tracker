# Portfolio Tracker - Comprehensive Project Analysis

## 📋 Executive Summary

**Portfolio Tracker** is a professional-grade portfolio management and analytics application written in Python. It combines:
- Clean layered architecture (Domain → Infrastructure → Services → Web)
- Real-time portfolio valuation with multi-currency support (USD/TWD)
- Advanced financial analytics (Volatility, Sharpe Ratio, Max Drawdown)
- Interactive web dashboard with Flask and HTMX
- CLI tools for automation and dry-run operations
- Persistent history tracking for performance analysis

---

## 🏗️ Architecture Overview

### Layered Design

```
┌─────────────────────────────────────────┐
│         Web Layer (Flask Routes)        │  - Dashboard rendering
│         (app/web/routes.py)             │  - REST endpoints
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│       Services Layer                    │  - PortfolioService
│  (app/services/)                        │  - AnalysisService
└─────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│    Infrastructure Layer                  │  - PriceFetcher
│   (app/infrastructure/)                  │  - HistoryRepository
│                                         │  - PortfolioRepository
└──────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│       Domain Layer                       │  - Models (dataclasses)
│    (app/domain/models.py)                │  - Business logic types
└──────────────────────────────────────────┘
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| **Domain Models** | `app/domain/models.py` | Data structures: `Asset`, `Stock`, `Cash`, `Portfolio`, `Totals`, `PositionBreakdown`, `PortfolioResult` |
| **Price Fetcher** | `app/infrastructure/market_data.py` | Fetches prices from Yahoo Finance, Stooq, TWSE; supports local overrides; in-memory caching (TTL: 5min) |
| **Persistence** | `app/infrastructure/persistence.py` | `HistoryRepository` (CSV), `PortfolioRepository` (JSON) |
| **Portfolio Service** | `app/services/portfolio_service.py` | Core valuation logic; currency conversion; position breakdown calculation |
| **Analysis Service** | `app/services/analysis_service.py` | Financial metrics: volatility, Sharpe ratio, max drawdown, beta, alpha |
| **Dependency Container** | `app/dependencies.py` | Singleton instances; environment-based configuration |
| **Web Routes** | `app/web/routes.py` | Flask blueprint; dashboard, CRUD endpoints |
| **Flask App Factory** | `app/__init__.py` | Application initialization |

---

## 🎯 Core Features & Functionality

### 1. **Multi-Currency Portfolio Valuation**
- **Supported Assets**: Stocks (Yahoo Finance, Stooq, TWSE) + Cash (USD, TWD)
- **Currency Conversion**: Automatic USD ↔ TWD conversion using `CurrencyConverter`
- **Smart Symbol Detection**: Recognizes `.TW` suffix for Taiwan stocks

**Flow**:
```
Portfolio (stocks + cash) 
  → Get prices for each stock → Convert to base currency (USD) 
  → Calculate position values → Sum totals → Return result
```

### 2. **Price Fetching System**
Hierarchical strategy:
1. **In-Memory Cache** (5-minute TTL) - Ultra-fast lookups
2. **Local Overrides** (price_overrides.json) - Manual prices
3. **Online Sources** (Yahoo Finance, Stooq, TWSE) - Live market data
4. **Batch Fetching** - Concurrent requests for multiple symbols

**Performance**: Pre-fetches all stock symbols in one batch call

### 3. **Portfolio History Tracking**
- **Storage**: CSV format (date, total_usd, total_twd, daily_return_pct)
- **Operations**: 
  - `load()` - Read history from disk
  - `upsert()` - Insert or update daily snapshot
  - Auto-calculation of daily returns
  - Historical data limited to 90 days in dashboard

### 4. **Financial Analytics**
Metrics calculated from historical data:
- **Volatility**: Annualized standard deviation (%)
- **Sharpe Ratio**: Risk-adjusted returns vs. risk-free rate (2%)
- **Max Drawdown**: Worst peak-to-trough decline (%)
- **Beta & Alpha**: Placeholder (1.0, 0.0) - Requires benchmark comparison

### 5. **Web Dashboard**
- **Tech Stack**: Flask + Jinja2 + Chart.js + HTMX
- **Dark Theme**: Professional, data-focused UI
- **Charts**: 
  - Portfolio allocation (pie chart)
  - Historical value (line chart)
  - Daily returns (line chart)
- **Interactive Features**: Date picker for historical view, live updates

### 6. **CLI Tool** (main.py)
Commands:
- `python main.py --dry-run` → View current portfolio value without saving
- `python main.py` → Append today's snapshot to history.csv

---

## 📊 Data Models

### Core Dataclasses
```python
@dataclass
class Stock(Asset):
    symbol: str              # e.g., "AAPL", "2330.TW"
    shares: float
    average_cost: float      # Purchase price

@dataclass
class Cash(Asset):
    currency: str            # "USD", "TWD"
    amount: float

@dataclass
class Portfolio:
    stocks: List[Stock]
    cash: List[Cash]

@dataclass
class PositionBreakdown:
    name: str
    category: str            # "Stock" or "Cash"
    value_usd: float
    value_twd: float
    portfolio_pct: float
    quantity: Optional[float]
    unit_price: Optional[float]
    average_cost: Optional[float]
    total_cost_usd: float
    total_cost_twd: float
    unrealized_pl_usd: float  # Profit/Loss
    unrealized_pl_twd: float
    roi_pct: float           # Return on Investment %

@dataclass
class PortfolioResult:
    totals: Totals           # Overall portfolio metrics
    positions: List[PositionBreakdown]  # Per-asset breakdown
```

---

## 📁 Configuration Files

### `portfolio.json`
Defines portfolio holdings:
```json
{
  "stocks": [
    { "symbol": "AAPL", "shares": 10, "average_cost": 150.0 },
    { "symbol": "2330.TW", "shares": 5, "average_cost": 300.0 }
  ],
  "cash": [
    { "currency": "USD", "amount": 1000.0 },
    { "currency": "TWD", "amount": 50000.0 }
  ]
}
```

### `price_overrides.json`
Manual price overrides (useful for assets not available online):
```json
{
  "000001.SS": 12.5,
  "LOCAL_STOCK": 100.0
}
```

### `history.csv`
Persistent daily snapshots:
```csv
date,total_usd,total_twd,daily_return_pct
2025-12-01,50000.00,1500000.00,0.00
2025-12-02,51000.00,1530000.00,2.00
2025-12-03,50500.00,1515000.00,-0.98
```

### `render.yaml`
Deployment configuration for Render.com:
- **Service**: Web (Python/Gunicorn)
- **Start Command**: `gunicorn dashboard_app:app`
- **Environment Variables**: PORTFOLIO_FILE, PRICE_OVERRIDES_FILE, HISTORY_FILE, OVERRIDES_ONLY

---

## 🔄 Data Flow Diagrams

### Dashboard Load Flow
```
Request: GET /
  ↓
Load portfolio.json → Portfolio object
  ↓
PortfolioService.calculate(portfolio)
  ├─ PriceFetcher.get_prices([symbols]) → Batch fetch + cache
  ├─ For each Stock: _value_stock() → USD/TWD values
  ├─ For each Cash: _value_cash() → Convert to USD
  └─ Return: PortfolioResult (totals + positions)
  ↓
Load history.csv → DataFrame
  ↓
Calculate metrics: volatility, sharpe, max_drawdown
  ↓
Render dashboard.html with data
  ↓
Response: HTML with charts + tables
```

### Daily Update Flow
```
CLI: python main.py
  ↓
PortfolioService.calculate() → PortfolioResult
  ↓
HistoryRepository.upsert(date, total_usd, total_twd)
  ├─ Load existing history.csv
  ├─ Update or append row for today
  ├─ Recalculate daily_return_pct
  └─ Save back to CSV
  ↓
Message: "Portfolio updated"
```

---

## 🚀 Deployment Strategy

### Local Development
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python dashboard_app.py
# Open http://127.0.0.1:5000
```

### macOS Note
Port 5000 conflicts with AirPlay. Solution:
```bash
export PORT=5001
python dashboard_app.py
```

### Production (Render.com)
- Managed by `render.yaml`
- Auto-deploys on push to main
- Requires `portfolio.json`, `price_overrides.json` in repo (or mount volumes)
- Gunicorn serves Flask app on port 5000

---

## 🛠️ Dependencies

| Package | Purpose |
|---------|---------|
| `flask` | Web framework |
| `yfinance` | Yahoo Finance price data |
| `pandas` | Data manipulation |
| `currency_converter` | USD ↔ TWD conversion |
| `requests` | HTTP library (Stooq, TWSE) |
| `gunicorn` | WSGI server (production) |
| `pytest` | Testing framework |
| `rich` | Terminal styling (CLI) |
| `matplotlib` | Charting (optional) |

---

## 💡 Key Implementation Details

### Price Caching Strategy
- **TTL**: 5 minutes per symbol
- **Storage**: In-memory dictionary `_cache: Dict[str, tuple[float, float]]`
- **Hit Rate**: Reduces API calls significantly during rapid portfolio views
- **Thread-Safe**: Concurrent requests pre-populate cache for all symbols

### Currency Conversion
- **Library**: `currency_converter` (fallback on missing/wrong dates)
- **Detection**: `.TW` suffix identifies TWD-denominated stocks
- **Rates**: Updated daily; historical rates available

### Portfolio Valuation Algorithm
1. Batch-fetch all stock prices
2. For each stock:
   - `price_usd = stock.price` or `price_usd = convert(stock.price_twd → USD)`
   - `value_usd = price_usd × shares`
   - `cost_usd = average_cost × shares` (in stock's currency, then converted)
   - `unrealized_pl = value_usd - cost_usd`
   - `roi_pct = unrealized_pl / cost_usd × 100`
3. For each cash:
   - `value_usd = cash.amount` (USD) or `convert(cash.amount_twd → USD)`
4. Sum all positions → portfolio totals

### Daily Return Calculation
```python
daily_return_pct = (today_total - yesterday_total) / yesterday_total × 100
```

---

## 🎓 Architecture Patterns Used

1. **Layered Architecture**: Clean separation of concerns
2. **Dependency Injection**: Singleton services injected via `dependencies.py`
3. **Repository Pattern**: Abstract data access (`HistoryRepository`, `PortfolioRepository`)
4. **Factory Pattern**: Flask app factory in `app/__init__.py`
5. **Service Locator**: `dependencies.py` acts as service registry
6. **Type Safety**: Full type hints with dataclasses

---

## 📈 Potential Improvements

### Short-Term (Quick Wins)
1. **Beta & Alpha Calculation**: Compare against SPY benchmark
2. **Error Handling**: Better exception messages for failed price fetches
3. **Unit Tests**: Add pytest fixtures for each layer
4. **Logging**: Structured logging with JSON output for debugging

### Medium-Term (Features)
1. **Portfolio Transactions**: Buy/sell order history
2. **Tax Reporting**: Cost basis tracking, realized gains
3. **Alerts**: Email notifications for price thresholds
4. **Multi-Portfolio**: Support multiple portfolios per user
5. **User Authentication**: Login system for shared deployments

### Long-Term (Architecture)
1. **Database**: Replace CSV with PostgreSQL for scalability
2. **Real-Time WebSockets**: Live price updates
3. **API First**: Separate backend API from web UI
4. **Microservices**: Price fetcher as independent service
5. **Mobile App**: React Native companion

---

## 🐛 Known Issues & Limitations

1. **Beta/Alpha**: Currently placeholder values (1.0, 0.0)
2. **Benchmark Data**: No benchmark comparison for risk analysis
3. **Historical Depth**: Limited to 90 days in dashboard (data still persisted)
4. **Currency Rates**: Depends on external API; no offline fallback
5. **Concurrent API Calls**: Could hit rate limits with large portfolios
6. **No Database**: CSV storage limits scalability

---

## 📞 Entry Points

### For CLI Users
```bash
python main.py --help           # Show options
python main.py --dry-run        # Preview current value
python main.py                  # Update history
```

### For Web Users
```bash
python dashboard_app.py         # Start web server
# Open browser to http://127.0.0.1:5000
```

### For Developers
```python
from app.dependencies import portfolio_service, price_fetcher
from app.infrastructure.persistence import PortfolioRepository

repo = PortfolioRepository()
portfolio = repo.load()
result = portfolio_service.calculate(portfolio)
print(result.totals)
```

---

## 📝 Summary

**Portfolio Tracker** is a well-architected portfolio management solution with:
- ✅ Clean layered design for maintainability
- ✅ Multi-currency support for global portfolios
- ✅ Professional financial metrics
- ✅ Both CLI and web interfaces
- ✅ Persistent history for trend analysis
- ✅ Production-ready deployment configuration

**Best For**: Individual investors, portfolio managers, financial advisors needing real-time portfolio valuation with historical analysis.

**Tech Stack**: Flask, yfinance, pandas, dataclasses, jinja2, Chart.js

**Production Status**: Ready for deployment (with Render.com or any WSGI host)
