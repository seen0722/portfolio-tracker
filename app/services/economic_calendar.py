"""Economic event calendar — upcoming high-impact US macro releases.

Pure and network-free: FOMC uses the published 2026 schedule, NFP is the
first Friday of each month (an exact rule), CPI is approximated to mid-month
and flagged as approximate (exact dates set by BLS). Knowing *when* these land
is the most actionable macro input — e.g. avoid adding size right before CPI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterator, List, Optional, Tuple

# Published 2026 FOMC decision days (second day of each meeting).
FOMC_2026: Tuple[date, ...] = (
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29), date(2026, 6, 17),
    date(2026, 7, 29), date(2026, 9, 16), date(2026, 10, 28), date(2026, 12, 9),
)


@dataclass(frozen=True)
class CalendarEvent:
    name: str
    date_iso: str
    days_until: int
    impact: str  # high / medium
    approximate: bool
    note: str

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "date": self.date_iso,
            "days_until": self.days_until,
            "impact": self.impact,
            "approximate": self.approximate,
            "note": self.note,
        }


def _first_friday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return date(year, month, 1 + (4 - first.weekday()) % 7)  # weekday 4 = Friday


def _months(today: date, n: int) -> Iterator[Tuple[int, int]]:
    year, month = today.year, today.month
    for _ in range(n + 1):
        yield year, month
        month += 1
        if month > 12:
            month, year = 1, year + 1


def nfp_dates(today: date, n: int = 3) -> List[date]:
    return [_first_friday(y, m) for y, m in _months(today, n)]


def cpi_dates(today: date, n: int = 3) -> List[date]:
    # Approximate: BLS releases CPI around mid-month (exact date varies).
    return [date(y, m, 13) for y, m in _months(today, n)]


def upcoming_events(today: date, limit: int = 5) -> List[CalendarEvent]:
    raw: List[Tuple[str, date, str, bool, str]] = []
    for d in FOMC_2026:
        raw.append(("FOMC 利率決議", d, "high", False, "Fed 利率與點陣圖"))
    for d in nfp_dates(today):
        raw.append(("非農就業 NFP", d, "high", False, "每月第一個週五"))
    for d in cpi_dates(today):
        raw.append(("CPI 通膨", d, "high", True, "約每月中旬,實際日期以 BLS 為準"))

    upcoming = sorted((e for e in raw if e[1] >= today), key=lambda e: e[1])
    return [
        CalendarEvent(
            name=name,
            date_iso=d.isoformat(),
            days_until=(d - today).days,
            impact=impact,
            approximate=approx,
            note=note,
        )
        for name, d, impact, approx, note in upcoming[:limit]
    ]


class EconomicCalendar:
    """Thin wrapper so the web layer depends on an injectable seam."""

    def upcoming(self, today: Optional[date] = None, limit: int = 5) -> List[CalendarEvent]:
        return upcoming_events(today or date.today(), limit)
