"""Unit tests for the capex service: table rendering and markdown auto-fill."""

from __future__ import annotations

from typing import List

import pytest

from app.infrastructure.capex_monitor import CapexMonitor, CapexQuarter, CapexSignal
from app.services.capex_service import AUTO_END, AUTO_START, CapexService


def _signal(symbol: str, light: str = "green", **kwargs) -> CapexSignal:
    defaults = dict(
        symbol=symbol,
        latest_period="2026-03-31",
        latest_capex=35.7e9,
        yoy_growth_pct=58.0,
        qoq_growth_pct=20.0,
        yoy_prev_growth_pct=40.0,
        trend="accelerating",
        light=light,
        next_earnings="2026-07-24",
        currency="USD",
        note="",
    )
    defaults.update(kwargs)
    return CapexSignal(**defaults)


def test_render_table_has_header_and_rows():
    service = CapexService(CapexMonitor())
    table = service.render_markdown_table([_signal("GOOGL"), _signal("MU", light="red")])
    assert "| 代號 |" in table
    assert "GOOGL" in table and "MU" in table
    assert "🟢" in table and "🔴" in table
    assert "35.7" in table  # capex rendered in billions
    assert "+58.0%" in table  # YoY formatted with sign
    assert "| 幣別 |" in table and "USD" in table  # reporting currency labelled


def test_render_table_handles_missing_values():
    service = CapexService(CapexMonitor())
    table = service.render_markdown_table(
        [_signal("X", light="unknown", latest_capex=None, yoy_growth_pct=None, latest_period=None)]
    )
    assert "⬜" in table
    assert "—" in table


def test_collect_preserves_requested_order(monkeypatch):
    monitor = CapexMonitor()

    def fake_get_signals(symbols: List[str]):
        return {sym: _signal(sym) for sym in symbols}

    monkeypatch.setattr(monitor, "get_signals", fake_get_signals)
    service = CapexService(monitor)
    signals = service.collect(["MU", "NVDA", "TSM"])
    assert [s.symbol for s in signals] == ["MU", "NVDA", "TSM"]


def test_update_markdown_file_replaces_auto_section(tmp_path):
    doc = tmp_path / "capex-monitor.md"
    doc.write_text(
        f"# Header\n\nintro\n\n{AUTO_START}\nOLD CONTENT\n{AUTO_END}\n\nfooter\n",
        encoding="utf-8",
    )
    service = CapexService(CapexMonitor())
    service.update_markdown_file(doc, [_signal("GOOGL")], as_of="2026-06-19")

    result = doc.read_text(encoding="utf-8")
    assert "OLD CONTENT" not in result
    assert "GOOGL" in result
    assert "最後自動更新：2026-06-19" in result
    assert result.startswith("# Header")
    assert result.rstrip().endswith("footer")
    # Markers preserved so the next run can replace again.
    assert result.count(AUTO_START) == 1
    assert result.count(AUTO_END) == 1


def test_update_markdown_file_raises_without_markers(tmp_path):
    doc = tmp_path / "no-markers.md"
    doc.write_text("# Header\n\nno markers here\n", encoding="utf-8")
    service = CapexService(CapexMonitor())
    with pytest.raises(ValueError):
        service.update_markdown_file(doc, [_signal("GOOGL")])
