"""Unit tests for the pure economic-event calendar."""

from datetime import date

from app.services.economic_calendar import (
    _first_friday,
    nfp_dates,
    upcoming_events,
)


def test_first_friday_is_a_friday():
    ff = _first_friday(2026, 7)
    assert ff.weekday() == 4  # Friday
    assert ff == date(2026, 7, 3)


def test_nfp_dates_are_all_fridays():
    for d in nfp_dates(date(2026, 6, 19)):
        assert d.weekday() == 4


def test_upcoming_events_are_future_and_sorted():
    today = date(2026, 6, 19)
    events = upcoming_events(today, limit=5)
    assert len(events) == 5
    dates = [e.date_iso for e in events]
    assert dates == sorted(dates)
    assert all(e.days_until >= 0 for e in events)


def test_next_event_is_july_nfp():
    today = date(2026, 6, 19)
    events = upcoming_events(today, limit=5)
    # first upcoming should be NFP on 2026-07-03
    assert events[0].name == "非農就業 NFP"
    assert events[0].date_iso == "2026-07-03"
    assert events[0].days_until == 14


def test_cpi_flagged_approximate():
    events = upcoming_events(date(2026, 6, 19), limit=6)
    cpi = next(e for e in events if e.name == "CPI 通膨")
    assert cpi.approximate is True
