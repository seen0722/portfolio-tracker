"""Unit tests for the SQLite NAV repository."""

import pandas as pd
import pytest

from app.infrastructure.nav_repository import NavRepository


@pytest.fixture
def nav_repo():
    repo = NavRepository(":memory:")
    yield repo
    repo.close()


def test_upsert_and_load_roundtrip(nav_repo):
    nav_repo.upsert("2026-01-02", 1000.0, 32000.0)
    nav_repo.upsert("2026-01-03", 1100.0, 35200.0)
    df = nav_repo.load()
    assert list(df["total_usd"]) == [1000.0, 1100.0]
    assert df["daily_return_pct"].iloc[1] == pytest.approx(10.0)


def test_upsert_replaces_same_date(nav_repo):
    nav_repo.upsert("2026-01-02", 1000.0, 32000.0)
    nav_repo.upsert("2026-01-02", 2000.0, 64000.0)
    df = nav_repo.load()
    assert nav_repo.count() == 1
    assert df["total_usd"].iloc[0] == 2000.0


def test_replace_all_overwrites_series(nav_repo):
    nav_repo.upsert("2026-01-01", 1.0, 32.0)
    new = pd.DataFrame(
        {
            "date": ["2026-02-01", "2026-02-02"],
            "total_usd": [500.0, 600.0],
            "total_twd": [16000.0, 19200.0],
        }
    )
    nav_repo.replace_all(new)
    df = nav_repo.load()
    assert nav_repo.count() == 2
    assert df["date"].tolist() == ["2026-02-01", "2026-02-02"]


def test_empty_load_returns_empty_frame(nav_repo):
    assert nav_repo.load().empty
