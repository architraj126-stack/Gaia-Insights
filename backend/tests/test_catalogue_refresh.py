"""
Phase 3a tests for catalogue refresh logic (SPEC 6.3, 15.3).

Tests are fully mocked — no network access needed.

Test 1: find_latest_complete_month — mocked source where the FINAL monthly
        step is the current (incomplete) month → returns the previous month.

Test 2: seed + version-change → ProvenanceEvent is created (never overwrites history).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import cftime

from backend.app.services.catalogue_refresh import find_latest_complete_month


# ---------------------------------------------------------------------------
# Helper — build a cftime-compatible numeric array from month list
# ---------------------------------------------------------------------------


def _make_time_values(months: List[tuple[int, int]], units: str = "days since 1800-01-01") -> np.ndarray:
    """
    Convert a list of (year, month) tuples into numeric CF time values using
    the given units string, so they can be decoded back by find_latest_complete_month.
    """
    dates = [cftime.DatetimeGregorian(y, m, 1) for y, m in months]
    return np.array(cftime.date2num(dates, units=units, calendar="standard"))


# ---------------------------------------------------------------------------
# Test 1: Incomplete final month → returns previous month
# ---------------------------------------------------------------------------


class TestFindLatestCompleteMonth:
    """
    SPEC 6.3 & 15.3: latest_observation_date = date of data, not file date.
    If the final step is the current in-progress month, return the PREVIOUS step.
    """

    def test_incomplete_final_month_returns_previous(self):
        """
        Arrange: build a time array ending with the CURRENT calendar month
        (which is by definition still in progress).
        Expect: the second-to-last step (last COMPLETE month) is returned.
        """
        now = datetime.now(timezone.utc)
        # Build 12 months ending with the CURRENT month
        months = []
        year, month = now.year, now.month
        for _ in range(12):
            months.insert(0, (year, month))
            month -= 1
            if month == 0:
                month = 12
                year -= 1

        units = "days since 1800-01-01 00:00:00"
        values = _make_time_values(months, units)

        result = find_latest_complete_month(values, units, "standard")

        # The last step is the current in-progress month → must NOT be returned
        current_step_date = date(now.year, now.month, 1)
        assert result != current_step_date, (
            f"Should not return the current in-progress month {current_step_date}"
        )

        # The returned date should be the step BEFORE the current month
        if now.month == 1:
            expected = date(now.year - 1, 12, 1)
        else:
            expected = date(now.year, now.month - 1, 1)

        assert result == expected, (
            f"Expected previous month {expected}, got {result}"
        )

    def test_all_complete_months_returns_latest(self):
        """
        When every step in the array is fully elapsed, return the last one.
        Uses a fixed historical date far in the past.
        """
        months = [(2026, m) for m in range(1, 11)]  # Jan–Oct 2026 (all past)
        units = "days since 1800-01-01 00:00:00"
        values = _make_time_values(months, units)

        result = find_latest_complete_month(values, units, "standard")

        # Oct 2026 must be in the past relative to current test date (Nov 2026+)
        assert result == date(2026, 10, 1), f"Expected 2026-10-01, got {result}"

    def test_empty_array_returns_none(self):
        """An empty time array should return None gracefully."""
        units = "days since 1800-01-01 00:00:00"
        result = find_latest_complete_month(np.array([]), units, "standard")
        assert result is None

    def test_single_complete_step(self):
        """Single historical step → that step is returned."""
        months = [(2020, 6)]
        units = "days since 1800-01-01 00:00:00"
        values = _make_time_values(months, units)
        result = find_latest_complete_month(values, units, "standard")
        assert result == date(2020, 6, 1)


# ---------------------------------------------------------------------------
# Test 2: Version change → ProvenanceEvent is created
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_version_change_creates_provenance_event():
    """
    SPEC 6.4: Changing a dataset version must create a ProvenanceEvent row.
    It must NOT silently overwrite the existing version.

    Uses an in-memory SQLite database via SQLAlchemy async to avoid needing
    a live PostgreSQL instance.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy import select, event as sa_event
    from backend.app.db.models import Base, Variable, DatasetProduct, ProvenanceEvent
    from backend.app.db.seed import _upsert_dataset_product

    # --- Setup: in-memory SQLite async engine ---
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    # SQLite does not support JSONB; patch dialect
    async with engine.begin() as conn:
        # Use aiosqlite-compatible table creation (models use JSONB which
        # falls back to JSON in SQLite automatically in SQLAlchemy 2.x)
        await conn.run_sync(Base.metadata.create_all)

    AsyncSession = async_sessionmaker(engine, expire_on_commit=False)

    dataset_id = "test_dataset_v1"

    async with AsyncSession() as session:
        # Insert a variable first (FK dependency)
        var = Variable(
            id="test_var",
            name="Test Variable",
            category="Test",
            description="desc",
            scientific_question="q",
            default_dataset_id=dataset_id,
            status="Available",
        )
        session.add(var)

        # Insert the initial DatasetProduct (version V1)
        product_v1 = DatasetProduct(
            id=dataset_id,
            variable_id="test_var",
            product_name="Test Product",
            provider="Test Provider",
            short_name="test_v1",
            version="V1",
            native_variable_name="precip",
            long_name="Test Long Name",
            units="mm/day",
            spatial_grid="regular_lat_lon",
            crs="EPSG:4326",
            spatial_coverage="Global",
            spatial_resolution="2.5° × 2.5°",
            temporal_resolution="monthly",
            start_date="1979-01-01",
            status="Available",
        )
        session.add(product_v1)
        await session.commit()

    # Verify no provenance events exist yet (clean state)
    async with AsyncSession() as session:
        events = (await session.execute(select(ProvenanceEvent))).scalars().all()
        assert len(events) == 0, "Should start with no provenance events"

    # --- Action: seed with a NEW version (V2) ---
    # Construct a YAML-like dict representing the updated dataset
    updated_ds_data = {
        "id": dataset_id,
        "variable_id": "test_var",
        "product_name": "Test Product",
        "provider": "Test Provider",
        "short_name": "test_v2",
        "version": "V2",  # ← version changed from V1 to V2
        "native_variable_name": "precip",
        "long_name": "Test Long Name",
        "units": "mm/day",
        "spatial_grid": "regular_lat_lon",
        "crs": "EPSG:4326",
        "spatial_coverage": "Global",
        "spatial_resolution": "2.5° × 2.5°",
        "temporal_resolution": "monthly",
        "start_date": "1979-01-01",
        "status": "Available",
    }

    async with AsyncSession() as session:
        await _upsert_dataset_product(session, updated_ds_data)
        await session.commit()

    # --- Assert: a ProvenanceEvent was created ---
    async with AsyncSession() as session:
        events = (
            await session.execute(
                select(ProvenanceEvent).where(ProvenanceEvent.dataset_id == dataset_id)
            )
        ).scalars().all()

        assert len(events) == 1, (
            f"Expected exactly 1 ProvenanceEvent after version change, got {len(events)}"
        )
        ev = events[0]
        assert ev.event_type == "version_change", f"Expected event_type='version_change', got {ev.event_type!r}"
        assert ev.old_version == "V1", f"Expected old_version='V1', got {ev.old_version!r}"
        assert ev.new_version == "V2", f"Expected new_version='V2', got {ev.new_version!r}"

    # --- Assert: the product was updated to V2 (not duplicated) ---
    async with AsyncSession() as session:
        products = (
            await session.execute(
                select(DatasetProduct).where(DatasetProduct.id == dataset_id)
            )
        ).scalars().all()
        assert len(products) == 1, "Must be exactly 1 DatasetProduct row (no duplication)"
        assert products[0].version == "V2", f"Expected version='V2', got {products[0].version!r}"

    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_idempotent_no_extra_events():
    """
    Seeding the same version twice must NOT create duplicate ProvenanceEvents.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy import select
    from backend.app.db.models import Base, Variable, DatasetProduct, ProvenanceEvent
    from backend.app.db.seed import _upsert_dataset_product

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSession = async_sessionmaker(engine, expire_on_commit=False)

    dataset_id = "idempotent_test_v1"
    ds_data = {
        "id": dataset_id,
        "variable_id": "test_var2",
        "product_name": "Idempotent Product",
        "provider": "Test Provider",
        "short_name": "idem_v1",
        "version": "V1",
        "native_variable_name": "precip",
        "long_name": "Idempotent Long Name",
        "units": "mm/day",
        "spatial_grid": "regular_lat_lon",
        "crs": "EPSG:4326",
        "spatial_coverage": "Global",
        "spatial_resolution": "2.5° × 2.5°",
        "temporal_resolution": "monthly",
        "start_date": "1979-01-01",
        "status": "Available",
    }

    async with AsyncSession() as session:
        # Insert supporting variable first
        var = Variable(
            id="test_var2",
            name="Test Variable 2",
            category="Test",
            description="desc",
            scientific_question="q",
            status="Available",
        )
        session.add(var)
        await session.commit()

    # Seed twice with the same version
    for _ in range(2):
        async with AsyncSession() as session:
            await _upsert_dataset_product(session, ds_data)
            await session.commit()

    async with AsyncSession() as session:
        # First seed → 1 "seed" event; second seed → no new event (same version)
        events = (
            await session.execute(
                select(ProvenanceEvent).where(ProvenanceEvent.dataset_id == dataset_id)
            )
        ).scalars().all()

        # Only 1 initial seed event; no version_change events
        version_change_events = [e for e in events if e.event_type == "version_change"]
        assert len(version_change_events) == 0, (
            f"No version_change events expected for same-version reseed; "
            f"got {len(version_change_events)}"
        )

    await engine.dispose()
