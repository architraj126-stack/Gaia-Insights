"""
Catalogue refresh service (SPEC 6.3, 15.3).

For each configured DatasetProduct, opens the data source (OPeNDAP or HTTP
NetCDF) and reads the native time coordinate to determine the newest
COMPLETE monthly step.

A monthly step is "complete" when the wall-clock time is AFTER the first
instant of the FOLLOWING month — i.e. the step itself has fully elapsed.

Two separate timestamps are stored (SPEC 15.3):
  latest_observation_date  — date of the most recent complete data step
  last_catalogue_check     — UTC wall-clock time we checked

If the final time step in the file is incomplete (e.g. the current month
in progress), we return the PREVIOUS step.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

import cftime
import numpy as np
import xarray as xr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import DatasetProduct, ProvenanceEvent

logger = logging.getLogger("backend.services.catalogue_refresh")


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def refresh_all_datasets(session: AsyncSession) -> dict[str, Any]:
    """
    Refresh latest_observation_date for every DatasetProduct that has an
    opendap_url or access_url.  Returns a summary dict keyed by dataset ID.
    """
    result = await session.execute(select(DatasetProduct))
    products = result.scalars().all()

    summary: dict[str, Any] = {}
    for product in products:
        url = product.opendap_url or product.access_url
        if not url:
            summary[product.id] = {
                "status": "skipped",
                "reason": "no access URL configured",
            }
            continue
        try:
            new_date = _fetch_latest_complete_month(url, product)
            summary[product.id] = await _update_product(session, product, new_date)
        except Exception as exc:
            logger.error("Refresh failed for %s: %s", product.id, exc, exc_info=True)
            summary[product.id] = {"status": "error", "detail": str(exc)}

    return summary


async def refresh_one_dataset(
    session: AsyncSession, dataset_id: str
) -> dict[str, Any]:
    """Refresh a single DatasetProduct by ID."""
    result = await session.execute(
        select(DatasetProduct).where(DatasetProduct.id == dataset_id)
    )
    product: Optional[DatasetProduct] = result.scalar_one_or_none()
    if product is None:
        return {"status": "error", "reason": f"Dataset {dataset_id!r} not found"}

    url = product.opendap_url or product.access_url
    if not url:
        return {"status": "skipped", "reason": "no access URL configured"}

    try:
        new_date = _fetch_latest_complete_month(url, product)
        return await _update_product(session, product, new_date)
    except Exception as exc:
        logger.error("Refresh failed for %s: %s", dataset_id, exc, exc_info=True)
        return {"status": "error", "detail": str(exc)}


# ---------------------------------------------------------------------------
# Core logic — separated so it can be unit-tested with mocked datasets
# ---------------------------------------------------------------------------


def find_latest_complete_month(time_values: np.ndarray, units: str, calendar: str = "standard") -> Optional[date]:
    """
    Given a raw numeric time array + CF units string, decode and return the
    most recent COMPLETE monthly step as a Python date object.

    A step is "complete" when the wall-clock time (UTC) is strictly after the
    first instant of the following month.  If the last step is incomplete
    (current month in progress), the previous step is returned.

    Returns None when the array is empty or no complete step exists.
    """
    if len(time_values) == 0:
        return None

    # Decode with cftime (avoids OutOfBoundsTimedelta from time_bnds fill values)
    decoded = cftime.num2date(time_values, units=units, calendar=calendar)

    # Sort descending — most datasets are already sorted ascending, but be safe
    decoded_sorted = sorted(decoded, key=lambda d: (d.year, d.month, d.day), reverse=True)

    now_utc = datetime.now(timezone.utc)

    for cf_dt in decoded_sorted:
        step_year = cf_dt.year
        step_month = cf_dt.month

        # Compute first instant of the NEXT month after this step
        if step_month == 12:
            next_month_year, next_month_month = step_year + 1, 1
        else:
            next_month_year, next_month_month = step_year, step_month + 1

        next_month_start = datetime(
            next_month_year, next_month_month, 1, tzinfo=timezone.utc
        )

        if now_utc > next_month_start:
            # This step is fully elapsed — it is a complete month
            return date(step_year, step_month, 1)

    return None


def _fetch_latest_complete_month(url: str, product: DatasetProduct) -> Optional[date]:
    """
    Open the dataset via xarray (OPeNDAP or HTTP) and return the most recent
    complete monthly step, using the data's own time coordinate.

    Uses decode_times=False + explicit cftime decoding to avoid the
    OutOfBoundsTimedelta bug documented in ADR-001.
    """
    logger.info("Fetching time coordinate from %s", url)

    # Open with minimal data — only load the time coordinate metadata
    try:
        ds = xr.open_dataset(url, decode_times=False, engine="netcdf4")
    except Exception as open_err:
        logger.warning("Could not open dataset at %s: %s", url, open_err)
        return None
    try:
        if "time" not in ds.coords and "time" not in ds:
            raise ValueError(f"No 'time' coordinate found in dataset at {url}")

        time_var = ds["time"]
        raw_values: np.ndarray = time_var.values
        units: str = time_var.attrs.get("units", "")
        calendar: str = time_var.attrs.get("calendar", "standard")

        if not units:
            raise ValueError(f"Time variable has no 'units' attribute at {url}")

        result = find_latest_complete_month(raw_values, units, calendar)
        logger.info("Latest complete month for %s: %s", product.id, result)
        return result
    finally:
        ds.close()


async def _update_product(
    session: AsyncSession,
    product: DatasetProduct,
    new_date: Optional[date],
) -> dict[str, Any]:
    """
    Persist the refreshed latest_observation_date.
    If the date changed, write a ProvenanceEvent (never overwrites old records).
    """
    old_date = product.latest_observation_date
    now_utc = datetime.now(timezone.utc)

    if new_date != old_date:
        logger.info(
            "latest_observation_date changed for %s: %s → %s",
            product.id,
            old_date,
            new_date,
        )
        session.add(
            ProvenanceEvent(
                dataset_id=product.id,
                event_type="refresh",
                old_latest_observation_date=old_date,
                new_latest_observation_date=new_date,
                detail={
                    "message": "Catalogue refresh updated latest_observation_date",
                    "checked_at": now_utc.isoformat(),
                },
            )
        )

    product.latest_observation_date = new_date
    product.last_catalogue_check = now_utc

    return {
        "status": "refreshed",
        "dataset_id": product.id,
        "latest_observation_date": new_date.isoformat() if new_date else None,
        "last_catalogue_check": now_utc.isoformat(),
        "changed": new_date != old_date,
    }
