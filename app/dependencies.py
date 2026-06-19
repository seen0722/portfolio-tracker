"""Dependency container — explicit wiring of adapters (Protocols) to services.

Replaces the old module-level singletons with one explicit Container so wiring is
visible in a single place and can be rebuilt for tests. The DI seam (build_container)
is the single swap point for adapters (US PriceFetcher now; EDGAR/intraday/FinMind later).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from app.infrastructure.capex_monitor import CapexMonitor
from app.infrastructure.history_provider import YahooHistoryProvider
from app.infrastructure.importer import import_portfolio_json
from app.infrastructure.ledger import SqliteLedger
from app.infrastructure.market_data import PriceFetcher
from app.infrastructure.nav_repository import NavRepository
from app.infrastructure.notifier import LogNotifier, TelegramNotifier
from app.services.advice_service import AdviceService
from app.services.analysis_service import AnalysisService
from app.services.capex_service import CapexService
from app.services.deterministic_narrator import DeterministicNarrator
from app.services.nav_service import NavService
from app.services.report_service import ReportService
from app.services.signal_orchestrator import SignalOrchestrator
from app.services.valuation_service import ValuationService
from app.signals.capex_adapter import CapexSignalAdapter
from app.signals.news_sentiment import NewsSentimentSignal
from app.signals.volume import VolumeSignal

logger = logging.getLogger(__name__)

PRICE_OVERRIDES_FILE = Path(os.environ.get("PRICE_OVERRIDES_FILE", "price_overrides.json"))
LEDGER_DB = os.environ.get("LEDGER_DB", "portfolio.db")
PORTFOLIO_FILE = Path(os.environ.get("PORTFOLIO_FILE", "portfolio.json"))
OVERRIDES_ONLY = os.environ.get("OVERRIDES_ONLY", "false").lower() == "true"


@dataclass
class Container:
    """The wired object graph the web layer depends on."""

    price_fetcher: PriceFetcher
    ledger: SqliteLedger
    valuation_service: ValuationService
    analysis_service: AnalysisService
    capex_service: CapexService
    nav_service: NavService
    signal_orchestrator: SignalOrchestrator
    advice_service: AdviceService
    report_service: ReportService


def build_container() -> Container:
    price_fetcher = PriceFetcher(
        overrides_path=PRICE_OVERRIDES_FILE,
        allow_online=not OVERRIDES_ONLY,
    )
    ledger = SqliteLedger(LEDGER_DB)
    _seed_if_empty(ledger)

    nav_service = NavService(
        ledger=ledger,
        history_provider=YahooHistoryProvider(),
        nav_repository=NavRepository(LEDGER_DB),
        price_provider=price_fetcher,
    )

    capex_monitor = CapexMonitor(allow_online=not OVERRIDES_ONLY)
    signal_orchestrator = SignalOrchestrator(
        [
            VolumeSignal(allow_online=not OVERRIDES_ONLY),
            CapexSignalAdapter(capex_monitor),
            NewsSentimentSignal(allow_online=not OVERRIDES_ONLY),
        ]
    )
    valuation_service = ValuationService(ledger, price_fetcher)
    advice_service = AdviceService(signal_orchestrator, _build_narrator())
    report_service = ReportService(
        valuation_service, nav_service, advice_service, _build_notifiers()
    )

    return Container(
        price_fetcher=price_fetcher,
        ledger=ledger,
        valuation_service=valuation_service,
        analysis_service=AnalysisService(price_fetcher),
        capex_service=CapexService(capex_monitor),
        nav_service=nav_service,
        signal_orchestrator=signal_orchestrator,
        advice_service=advice_service,
        report_service=report_service,
    )


def _build_notifiers():
    """Telegram push when configured, plus an always-on log fallback."""
    notifiers = []
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        notifiers.append(TelegramNotifier(token, chat_id))
    notifiers.append(LogNotifier())
    return notifiers


def _build_narrator():
    """LLM narrator when LLM_API_KEY is set; deterministic fallback otherwise."""
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        return DeterministicNarrator()
    from app.infrastructure.llm_client import LlmNarratorClient

    narrator = LlmNarratorClient(
        api_key=api_key,
        model=os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001"),
        provider=os.environ.get("LLM_PROVIDER", "anthropic"),
    )
    try:
        narrator.validate()
    except Exception as exc:  # fall back rather than break startup
        logger.warning("LLM narrator disabled (%s); using deterministic narrator.", exc)
        return DeterministicNarrator()
    logger.info("Using LLM narrator: %s", narrator.model)
    return narrator


def _seed_if_empty(ledger: SqliteLedger) -> None:
    """One-shot migration: seed an empty ledger from portfolio.json if present."""
    if ledger.count() > 0:
        return
    if not PORTFOLIO_FILE.exists():
        logger.info("No %s found; starting with an empty ledger.", PORTFOLIO_FILE)
        return
    try:
        summary = import_portfolio_json(PORTFOLIO_FILE, ledger)
        logger.info("Seeded ledger from %s: %s", PORTFOLIO_FILE, summary)
    except Exception as exc:  # never block app startup on a bad seed file
        logger.warning("Failed to seed ledger from %s: %s", PORTFOLIO_FILE, exc)


container = build_container()
