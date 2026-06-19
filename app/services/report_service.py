"""ReportService — assemble the daily report end-to-end and dispatch it.

Pulls the live valuation, records/reads the NAV series, runs the advice layer,
builds the report, and pushes it through the configured notifiers.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import List, Sequence

from app.services.advice_service import AdviceService
from app.services.nav_service import NavService
from app.services.report_builder import ReportContent, build_report
from app.services.valuation_service import ValuationService

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(
        self,
        valuation_service: ValuationService,
        nav_service: NavService,
        advice_service: AdviceService,
        notifiers: Sequence[object],
    ) -> None:
        self.valuation_service = valuation_service
        self.nav_service = nav_service
        self.advice_service = advice_service
        self.notifiers = list(notifiers)

    def generate(self) -> ReportContent:
        result = self.valuation_service.value()
        as_of = date.today().isoformat()

        self.nav_service.ensure_history()
        self.nav_service.snapshot(result.totals.usd, result.totals.twd, as_of)
        history = self.nav_service.history()
        daily_return = (
            float(history["daily_return_pct"].iloc[-1]) if not history.empty else 0.0
        )

        stock_positions = [p for p in result.positions if p.category == "stock"]
        symbols = [p.name for p in stock_positions]
        contexts = {p.name: {"roi_pct": p.roi_pct} for p in stock_positions}
        cards = self.advice_service.advise_many(symbols, contexts)

        return build_report(result, cards, as_of, daily_return)

    def send(self) -> ReportContent:
        report = self.generate()
        delivered: List[str] = []
        for notifier in self.notifiers:
            try:
                if notifier.send(report.title, report.text):
                    delivered.append(getattr(notifier, "name", "?"))
            except Exception as exc:  # one bad channel must not block the rest
                logger.warning("Notifier %s failed: %s", getattr(notifier, "name", "?"), exc)
        logger.info("Daily report dispatched via: %s", ", ".join(delivered) or "none")
        return report
