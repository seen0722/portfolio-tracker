# Portfolio Analyst

A professional-grade portfolio tracking and analysis tool featuring a layered architecture, advanced financial metrics, and a minimalist agile UI.

## Features

### 🏗️ Modern Architecture
- **Layered Design**: Clean separation of concerns (Domain, Infrastructure, Services, Web).
- **Dependency Injection**: Modular components for easy testing and extensibility.
- **Type Safety**: Fully typed Python codebase using `dataclasses` and `typing`.

### 📊 Professional Analytics
- **Advanced Metrics**: Real-time calculation of Volatility, Sharpe Ratio, Max Drawdown, and Beta.
- **Performance Grid**: Heatmap-style visualization of asset performance.
- **Interactive Charts**: Dynamic History and Allocation charts using Chart.js.

### ⚡ High Performance
- **Concurrent Fetching**: Parallel price fetching for rapid updates.
- **Caching**: In-memory caching with TTL to minimize API latency.
- **Optimized Calculation**: Batch processing for portfolio valuations.

### 🎨 Minimalist Agile UI
- **Dark Theme**: Sleek, professional design focused on data readability.
- **Responsive Layout**: Sidebar navigation with a mobile-friendly grid system.
- **HTMX Interactions**: Fast, dynamic updates without full page reloads.

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd portfolio-tracker
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Web Dashboard (Recommended)

Start the web application to view your portfolio analytics:

```bash
python dashboard_app.py
```

Open your browser and navigate to `http://127.0.0.1:5000`.

> **Note for macOS Users**: If you see an "Address already in use" error, port 5000 is likely taken by AirPlay Receiver. You can run on a different port:
> ```bash
> export PORT=5001
> python dashboard_app.py
> ```
> Then access `http://127.0.0.1:5001`.

### CLI Tool

Run the command-line interface for quick updates or automation:

```bash
# Dry run (view current value without saving history)
python main.py --dry-run

# Update history (append today's value to history.csv)
python main.py
```

## Configuration

### `portfolio.json`
Define your portfolio holdings. Supports Stocks and Cash.

```json
{
    "stocks": [
        { "symbol": "AAPL", "shares": 10, "average_cost": 150.0 },
        { "symbol": "NVDA", "shares": 5, "average_cost": 400.0 }
    ],
    "cash": [
        { "currency": "USD", "amount": 1000.0 },
        { "currency": "TWD", "amount": 50000.0 }
    ]
}
```

### `price_overrides.json` (Optional)
Manually set prices for assets that cannot be fetched online.

```json
{
    "000001.SS": 12.5
}
```

## Project Structure

```
app/
├── domain/         # Core business models (Portfolio, Stock, Cash)
├── infrastructure/ # External adapters (PriceFetcher, Repositories)
├── services/       # Business logic (PortfolioService, AnalysisService)
└── web/            # Flask routes and views
static/             # CSS and assets
templates/          # HTML templates
main.py            # CLI entry point
dashboard_app.py   # Web app entry point
```

## Deployment

### Vultr / Ubuntu VPS
Use the provided `deploy.sh` script to deploy to a VPS:

```bash
./deploy.sh <repo_url> <domain>
```

### Render
The project includes a `render.yaml` for easy deployment on Render.com.
