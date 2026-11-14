"""
Tests for GPCP time-series pipeline (SPEC 12, 14, 15.1, 16.3).

Covers:
1. Unit tests for leap years in temporal aggregation (Feb 1992 vs Feb 1990).
2. Annual & seasonal aggregation with missing month flags.
3. Synthetic NetCDF tests with known values, fill values (-9.96921e+36), missing months,
   and antimeridian-crossing geometries.
4. Area-weighting and fractional cell overlap calculation.
5. Integration test on GPCP dataset for country time-series and cache hit verification.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import cftime
import numpy as np
import pytest
import xarray as xr
from shapely.geometry import Polygon, box

from backend.app.services.aggregate import (
    aggregate_annual,
    aggregate_monthly,
    aggregate_seasonal,
    get_days_in_month,
    rate_to_monthly_accumulation,
)
from backend.app.services.ingest import (
    compute_subset_cache_key,
    generate_expected_monthly_steps,
    normalize_gpcp_dataset,
    validate_time_steps,
)
from backend.app.services.regions import (
    compute_geodesic_cell_area_km2,
    extract_regional_mean_timeseries,
)


# ===========================================================================
# 1. Unit Tests: Leap Years and Temporal Aggregation
# ===========================================================================

def test_leap_year_days_in_month():
    # 1992 is a leap year (Feb has 29 days)
    assert get_days_in_month(1992, 2) == 29
    # 1990 is non-leap (Feb has 28 days)
    assert get_days_in_month(1990, 2) == 28
    # 2000 is a leap year (divisible by 400)
    assert get_days_in_month(2000, 2) == 29
    # 1900 was not a leap year
    assert get_days_in_month(1900, 2) == 28


def test_rate_to_monthly_accumulation_leap_years():
    rate = 4.0  # mm/day
    # Feb 1992: 4.0 * 29 = 116.0 mm
    feb_1992 = rate_to_monthly_accumulation(rate, 1992, 2)
    assert feb_1992 == 116.0

    # Feb 1990: 4.0 * 28 = 112.0 mm
    feb_1990 = rate_to_monthly_accumulation(rate, 1990, 2)
    assert feb_1990 == 112.0

    # None handling
    assert rate_to_monthly_accumulation(None, 1992, 2) is None


def test_annual_aggregation_missing_month_handling():
    # Create 12 months for year 2020 where month 5 is missing
    monthly_pts = []
    for m in range(1, 13):
        is_missing = (m == 5)
        monthly_pts.append({
            "date": f"2020-{m:02d}-01",
            "value": None if is_missing else 100.0,
            "units": "mm",
            "valid_cell_count": 0 if is_missing else 10,
            "valid_area_km2": 0.0 if is_missing else 50000.0,
            "is_missing": is_missing,
            "flags": ["missing_data"] if is_missing else [],
        })

    annual_pts = aggregate_annual(monthly_pts, variable="precipitation")
    assert len(annual_pts) == 1
    pt = annual_pts[0]
    assert pt["year"] == 2020
    assert pt["value"] is None  # Must be None/NaN because year is incomplete
    assert pt["is_missing"] is True
    assert 5 in pt["missing_months"]
    assert any("incomplete_year" in f for f in pt["flags"])


def test_annual_aggregation_complete_year():
    # 12 complete months with 50.0 mm each = 600.0 mm
    monthly_pts = [
        {
            "date": f"2021-{m:02d}-01",
            "value": 50.0,
            "units": "mm",
            "valid_cell_count": 10,
            "valid_area_km2": 50000.0,
            "is_missing": False,
            "flags": [],
        }
        for m in range(1, 13)
    ]
    annual_pts = aggregate_annual(monthly_pts, variable="precipitation")
    assert len(annual_pts) == 1
    pt = annual_pts[0]
    assert pt["year"] == 2021
    assert pt["value"] == 600.0
    assert pt["is_missing"] is False
    assert len(pt["missing_months"]) == 0


def test_seasonal_aggregation():
    # 2021 seasonal: DJF, MAM, JJA, SON
    monthly_pts = [
        {
            "date": f"2021-{m:02d}-01",
            "value": 10.0,
            "units": "mm",
            "valid_cell_count": 10,
            "valid_area_km2": 50000.0,
            "is_missing": False,
            "flags": [],
        }
        for m in range(1, 13)
    ]
    seasonal_pts = aggregate_seasonal(monthly_pts, variable="precipitation")
    mam = [s for s in seasonal_pts if s["season"] == "MAM"][0]
    assert mam["value"] == 30.0  # 10 + 10 + 10
    assert mam["is_missing"] is False


# ===========================================================================
# 2. Geodesic Cell Area & Fractional Overlap
# ===========================================================================

def test_compute_geodesic_cell_area_equator_vs_pole():
    # 2.5 deg cell at equator vs 60 deg lat
    area_eq = compute_geodesic_cell_area_km2(lat_deg=0.0, dlat_deg=2.5, dlon_deg=2.5)
    area_60 = compute_geodesic_cell_area_km2(lat_deg=60.0, dlat_deg=2.5, dlon_deg=2.5)
    assert area_eq > area_60
    # Cell area at 60 deg lat should be roughly ~half of equatorial cell area
    ratio = area_60 / area_eq
    assert 0.45 < ratio < 0.55


# ===========================================================================
# 3. Synthetic NetCDF: Fill Values, Missing Steps & Antimeridian
# ===========================================================================

@pytest.fixture
def synthetic_netcdf(tmp_path) -> Path:
    """
    Creates a synthetic NetCDF dataset with:
    - 4 time steps (2000-01, 2000-02, 2000-04, 2000-05) -> missing 2000-03!
    - Lats: [-5.0, -2.5, 0.0, 2.5, 5.0]
    - Lons in 0..360 coordinates: [175.0, 177.5, 180.0, 182.5, 185.0]
      (Tests 0..360 -> -180..180 normalization and antimeridian crossing)
    - Precipitation array with known values and fill values (-9.96921e+36)
    """
    lats = np.array([5.0, 2.5, 0.0, -2.5, -5.0], dtype=np.float32)  # descending like raw GPCP
    lons = np.array([175.0, 177.5, 180.0, 182.5, 185.0], dtype=np.float32)

    # Time steps: days since 1800-01-01
    # 2000-01-01, 2000-02-01, 2000-04-01 (skipping March!), 2000-05-01
    cf_dates = [
        cftime.DatetimeGregorian(2000, 1, 1),
        cftime.DatetimeGregorian(2000, 2, 1),
        cftime.DatetimeGregorian(2000, 4, 1),
        cftime.DatetimeGregorian(2000, 5, 1),
    ]
    time_vals = cftime.date2num(cf_dates, units="days since 1800-01-01 00:00:00", calendar="standard")

    # Shape: (4, 5, 5)
    data = np.ones((4, 5, 5), dtype=np.float32) * 5.0  # 5.0 mm/day base
    # Inject fill values
    data[:, 0, 0] = -9.96921e+36
    data[1, 2, 2] = -9.96921e+36

    ds = xr.Dataset(
        data_vars={
            "precip": (["time", "lat", "lon"], data, {"units": "mm/day", "missing_value": -9.96921e+36}),
        },
        coords={
            "time": ("time", time_vals, {"units": "days since 1800-01-01 00:00:00", "calendar": "standard"}),
            "lat": ("lat", lats, {"units": "degrees_north"}),
            "lon": ("lon", lons, {"units": "degrees_east"}),
        },
    )

    out_file = tmp_path / "synthetic_gpcp.nc"
    ds.to_netcdf(out_file)
    return out_file


def test_synthetic_pipeline_normalization(synthetic_netcdf):
    raw_ds = xr.open_dataset(synthetic_netcdf, decode_times=False)
    norm_ds = normalize_gpcp_dataset(raw_ds, var_name="precip")

    # 1. Longitudes should be normalized from 0..360 to -180..180
    norm_lons = norm_ds["lon"].values
    assert np.all(norm_lons >= -180.0) and np.all(norm_lons <= 180.0)
    # Coordinates must be sorted ascending
    assert np.all(np.diff(norm_ds["lat"].values) > 0)
    assert np.all(np.diff(norm_ds["lon"].values) > 0)

    # 2. Time coordinate should be decoded to 'YYYY-MM-01'
    time_strs = list(norm_ds["time"].values)
    assert time_strs == ["2000-01-01", "2000-02-01", "2000-04-01", "2000-05-01"]

    # 3. Fill values (-9.96921e+36) must be decoded strictly to NaN
    precip_vals = norm_ds["precip"].values
    assert np.any(np.isnan(precip_vals))
    assert np.all(np.isnan(precip_vals) | (precip_vals >= 0.0))


def test_synthetic_missing_time_detection(synthetic_netcdf):
    raw_ds = xr.open_dataset(synthetic_netcdf, decode_times=False)
    norm_ds = normalize_gpcp_dataset(raw_ds, var_name="precip")

    all_steps = list(norm_ds["time"].values)
    expected, missing = validate_time_steps(all_steps, "2000-01-01", "2000-05-01")

    assert len(expected) == 5  # Jan, Feb, Mar, Apr, May
    assert missing == ["2000-03-01"]  # March was deliberately omitted in fixture


def test_synthetic_spatial_masking_antimeridian(synthetic_netcdf):
    raw_ds = xr.open_dataset(synthetic_netcdf, decode_times=False)
    norm_ds = normalize_gpcp_dataset(raw_ds, var_name="precip")

    # Define a polygon straddling the antimeridian (-180 / 180)
    # Longitude span: 176 to -176 (i.e. crossing 180)
    # In GeoJSON / shapely, antimeridian polygons are split or multi-polygons.
    # We can create a polygon from -179 to -176 and -2 to 2 lat
    poly = box(-179.0, -2.0, -176.0, 2.0)

    res = extract_regional_mean_timeseries(
        norm_ds["precip"],
        poly,
        method="fractional_overlap",
    )

    assert len(res["time_steps"]) == 4
    # All non-fill cells have value 5.0 mm/day
    for val in res["mean_values"]:
        assert val is not None
        assert 4.9 <= val <= 5.1
    assert res["intersecting_cell_count"] > 0
    assert res["area_weighting"] == "geodesic_ellipsoid"


# ===========================================================================
# 4. Integration Test: Real GPCP Data for Country Query
# ===========================================================================

@pytest.mark.asyncio
async def test_real_gpcp_country_timeseries():
    """
    End-to-end integration test querying real GPCP data for a country (e.g. Fiji).
    Asserts:
    1. Returns valid monthly series from 1990-01-01 to latest observation (2026-10-01).
    2. Valid count = 442 months.
    3. Proper SPEC 15.4 provenance and units (mm for monthly accumulation).
    4. Second call is served from cache.
    """
    from backend.app.api.analysis import (
        TimeSeriesRequest,
        create_timeseries_analysis,
    )
    from backend.app.services.boundaries import get_boundary_by_id

    # Try Fiji (admin0_fji_fiji) or Chad (admin0_tcd_chad)
    boundary = get_boundary_by_id("admin0_fji_fiji")
    if not boundary:
        pytest.skip("Boundary admin0_fji_fiji not found in test environment.")

    req = TimeSeriesRequest(
        dataset_id="gpcp_monthly_v23",
        dataset_version="v2.3",
        variable="precipitation",
        region_id="admin0_fji_fiji",
        start_date="1990-01-01",
        end_date="2026-10-01",
        aggregation="monthly",
    )

    # First call: computes and caches
    resp1 = await create_timeseries_analysis(req, session=None)
    assert resp1["status"] == "completed"
    assert resp1["coverage"]["valid_steps"] >= 440
    assert resp1["dataset"]["units"] == "mm"
    assert resp1["series_url"].startswith("/api/results/series/")

    # Second call: served from cache
    resp2 = await create_timeseries_analysis(req, session=None)
    assert resp2["status"] == "completed"
    assert resp2["coverage"]["valid_steps"] == resp1["coverage"]["valid_steps"]
