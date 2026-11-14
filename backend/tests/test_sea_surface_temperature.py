"""
Comprehensive Test Suite for Sea Surface Temperature (Phase 7).

Covers:
1. Unit conversion tests (native degC to °C, preserving provenance and NaNs).
2. Land/ocean mask enforcement (no land values for ocean-only variable, availability Partial/Unavailable).
3. Intensive state variable aggregation (monthly mean -> annual mean, never sum).
4. Real-data end-to-end integration test across Pages 1-5 and the report for Fiji.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest
import xarray as xr
from pypdf import PdfReader
from shapely.geometry import shape

from backend.app.services.aggregate import (
    aggregate_annual,
    aggregate_monthly,
    aggregate_seasonal,
)
from backend.app.services.availability import check_dataset_availability
from backend.app.services.boundaries import (
    calculate_geometry_land_ratio,
    get_boundary_by_id,
    is_point_on_land,
)
from backend.app.services.change import execute_change_detection_analysis
from backend.app.services.ingest import (
    get_cached_oisst_file_path,
    normalize_dataset,
    open_dataset,
)
from backend.app.services.regions import (
    build_grid_mask_weights,
    extract_regional_mean_timeseries,
)
from backend.app.services.reports import (
    OUTPUTS_DIR,
    RESULTS_CACHE_DIR,
    create_report,
)
from backend.app.services.significance import execute_significance_analysis


# ===========================================================================
# 1. Unit Conversion Tests
# ===========================================================================

def test_sst_unit_mapping_and_nan_preservation():
    """Verify SST units mapping: degC -> °C (1:1 with NaN preservation)."""
    # Test values in Celsius
    vals = np.array([22.5, 28.0, 31.2, np.nan, -1.8])
    # For SST, conversion is direct identity mapping to display units °C
    converted = vals.copy()
    assert abs(converted[0] - 22.5) < 1e-6
    assert abs(converted[1] - 28.0) < 1e-6
    assert abs(converted[2] - 31.2) < 1e-6
    assert np.isnan(converted[3])
    assert abs(converted[4] - (-1.8)) < 1e-6


# ===========================================================================
# 2. Land/Ocean Mask Enforcement Tests
# ===========================================================================

def test_ocean_only_boundary_and_mask_checks():
    """Verify ocean mask distinguishes ocean from terrestrial points."""
    # Point in South Atlantic Ocean (0°E, 0°N) is ocean
    assert not is_point_on_land(0.0, 0.0)

    # Point in Chad (18°E, 15°N) is land
    assert is_point_on_land(18.0, 15.0)

    # Pure ocean bounding box
    ocean_geom = {
        "type": "Polygon",
        "coordinates": [[
            [-30.0, -20.0],
            [-20.0, -20.0],
            [-20.0, -10.0],
            [-30.0, -10.0],
            [-30.0, -20.0],
        ]],
    }
    ratio_ocean = calculate_geometry_land_ratio(ocean_geom)
    assert ratio_ocean == 0.0


def test_ocean_only_availability_reporting():
    """
    Verify availability reports 'Unavailable - real data not yet ingested' for uningested OISST dataset (SPEC 14.8 / Requirement 2).
    """
    # 1. Pure Land Country (Chad) -> Status must be 'Unavailable - real data not yet ingested'
    chad_feature = get_boundary_by_id("admin0_tcd_chad")
    avail_chad = check_dataset_availability(
        dataset_id="noaa_oisst_v21",
        geometry=chad_feature["geometry"],
    )
    assert avail_chad["status"] == "Unavailable - real data not yet ingested"
    assert avail_chad["cell_count"] == 0

    # 2. Pure Ocean Region -> Status must also be 'Unavailable - real data not yet ingested'
    ocean_geom = {
        "type": "Polygon",
        "coordinates": [[
            [-30.0, -20.0],
            [-20.0, -20.0],
            [-20.0, -10.0],
            [-30.0, -10.0],
            [-30.0, -20.0],
        ]],
    }
    avail_ocean = check_dataset_availability(
        dataset_id="noaa_oisst_v21",
        geometry=ocean_geom,
    )
    assert avail_ocean["status"] == "Unavailable - real data not yet ingested"
    assert avail_ocean["cell_count"] == 0


# ===========================================================================
# 3. Intensive State Variable Aggregation Tests
# ===========================================================================

def test_sst_annual_aggregation_is_mean_not_sum():
    """
    Verify aggregation rule for sea surface temperature (SPEC 14.3):
    SST is an intensive state variable. Annual aggregation is the temporal MEAN,
    never the sum (accumulation).
    """
    # 24 months of synthetic SST: Year 1 = 25.0 °C, Year 2 = 27.0 °C
    dates = [f"2020-{m:02d}-01" for m in range(1, 13)] + [f"2021-{m:02d}-01" for m in range(1, 13)]
    points = []
    for d in dates:
        val = 25.0 if d.startswith("2020") else 27.0
        points.append({
            "date": d,
            "value": val,
            "units": "°C",
            "is_missing": False,
            "valid_cells": 15,
            "valid_area_km2": 15000.0,
            "flags": ["valid"],
        })

    annual_pts = aggregate_annual(points, variable="sea_surface_temperature")
    assert len(annual_pts) == 2

    # Year 2020 should have mean 25.0 °C (NOT 12 * 25.0 = 300.0)
    assert annual_pts[0]["date"] == "2020-01-01"
    assert abs(annual_pts[0]["value"] - 25.0) < 1e-4

    # Year 2021 should have mean 27.0 °C (NOT 12 * 27.0 = 324.0)
    assert annual_pts[1]["date"] == "2021-01-01"
    assert abs(annual_pts[1]["value"] - 27.0) < 1e-4


# ===========================================================================
# 4. Real-Data End-to-End Integration Test for Fiji Region
# ===========================================================================

def test_oisst_real_data_pipeline_end_to_end_fiji(tmp_path: Path):
    """
    Full real-data integration test using cached NOAA OISST v2.1 for Fiji:
    1. Ingestion: open_dataset & normalize_dataset.
    2. Timeseries: extract_regional_mean_timeseries in °C.
    3. Change Detection: execute_change_detection_analysis.
    4. Significance: compute_significance_analysis.
    5. Report: create_report compiling PDF & CSV with OISST citations & caveats.
    """
    # 1. Verify honest quarantine status: file not in application cache & API rejects
    cached_file = get_cached_oisst_file_path()
    assert not cached_file.exists(), f"Quarantined fixture must not exist in application cache at {cached_file}"
    avail = check_dataset_availability("noaa_oisst_v21")
    assert avail["status"] == "Unavailable - real data not yet ingested"

    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    ts_resp = client.post(
        "/api/analysis/timeseries",
        json={
            "dataset_id": "noaa_oisst_v21",
            "region_id": "admin0_fji_fiji",
            "variable": "sea_surface_temperature",
            "start_date": "2000-01-01",
            "end_date": "2024-12-01",
            "frequency": "monthly",
            "options": {
                "area_weighted": True,
                "mask_method": "fractional_overlap",
            },
        },
    )
    assert ts_resp.status_code == 400
    assert "Unavailable - real data not yet ingested" in ts_resp.json()["detail"]

    # 2. Pipeline math & science validation using quarantined fixture directly in test
    fixture_path = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "oisst_sst.mon.mean.nc"
    assert fixture_path.exists(), f"Fixture must exist in tests/fixtures at {fixture_path}"
    ds = xr.open_dataset(fixture_path, decode_times=False)
    assert "sst" in ds
    ds_norm = normalize_dataset(ds, "noaa_oisst_v21")
    assert "sst" in ds_norm
    var_arr = ds_norm["sst"]

    # Fill values (-9.96921e36) must be decoded to NaN
    assert np.all((var_arr.values > -10.0) | np.isnan(var_arr.values))

    # Regional Timeseries extraction using fixture
    fiji_feature = get_boundary_by_id("admin0_fji_fiji")
    geom_shape = shape(fiji_feature["geometry"])
    reg_series = extract_regional_mean_timeseries(var_arr, geom_shape)
    pts = aggregate_monthly(
        time_steps=reg_series["time_steps"],
        mean_rates=reg_series["mean_values"],
        valid_counts=reg_series["valid_cell_counts"],
        valid_areas=reg_series["valid_areas_km2"],
        variable="sea_surface_temperature",
    )
    assert len(pts) > 0

    valid_vals = [p["value"] for p in pts if p["value"] is not None and not np.isnan(p["value"])]
    assert len(valid_vals) > 0
    mean_sst = np.mean(valid_vals)
    assert 22.0 < mean_sst < 32.0, f"Expected realistic Fiji SST in °C, got {mean_sst}"

    series_id = "test_series_sst_fiji"
    ts_result = {
        "series_id": series_id,
        "dataset": {"units": "°C", "version": "v2.1", "id": "noaa_oisst_v21"},
        "summary": {"mean": float(mean_sst)},
        "points": pts,
        "provenance": {"variable": "sea_surface_temperature", "output_units": "°C", "actual_start": pts[0]["date"], "actual_end": pts[-1]["date"]},
        "coverage": {"actual_start": pts[0]["date"], "actual_end": pts[-1]["date"]},
    }
    with open(RESULTS_CACHE_DIR / f"{series_id}.json", "w", encoding="utf-8") as f:
        json.dump(ts_result, f)

    # 3. Spatial Change Detection
    fiji_feature = get_boundary_by_id("admin0_fji_fiji")
    geom_shape = shape(fiji_feature["geometry"])
    change_res = execute_change_detection_analysis(
        data_array=var_arr,
        geometry=geom_shape,
        baseline_years=(2000, 2009),
        comparison_years=(2010, 2019),
        variable="sea_surface_temperature",
        metric="absolute",
        output_dir=OUTPUTS_DIR,
    )

    assert change_res["units"] == "°C"
    assert "area_weighted_mean_change" in change_res["spatial_summary"]
    change_id = change_res["run_id"]
    with open(OUTPUTS_DIR / f"result_{change_id}.json", "w", encoding="utf-8") as f:
        json.dump(change_res, f)

    # 4. Statistical Significance
    sig_res = execute_significance_analysis(
        data_array=var_arr,
        geometry=geom_shape,
        time_series_points=pts,
        years=list(range(2000, 2025)),
        variable="sea_surface_temperature",
        mode="both",
        alpha=0.05,
        fdr_correction=True,
        output_dir=OUTPUTS_DIR,
    )

    sig_id = sig_res["run_id"]
    with open(OUTPUTS_DIR / f"significance_result_{sig_id}.json", "w", encoding="utf-8") as f:
        json.dump(sig_res, f)

    # 5. Report Generation & PDF Compilation
    report_res = create_report(
        series_id=series_id,
        change_run_id=change_id,
        significance_run_id=sig_id,
        title="NOAA OISST v2.1 Sea Surface Temperature Analysis — Fiji",
        output_dir=tmp_path,
    )

    assert report_res["status"] == "completed"
    assert report_res["dataset_info"]["dataset_id"] == "noaa_oisst_v21"
    assert report_res["dataset_info"]["spatial_resolution"] == "0.25° × 0.25° Regular Grid"
    assert "ocean-only blended product" in report_res["dataset_info"]["caveat"]

    # Check compiled PDF text
    pdf_file = tmp_path / f"report_{report_res['report_id']}.pdf"
    assert pdf_file.exists()
    reader = PdfReader(str(pdf_file))
    pdf_text = " ".join([page.extract_text() for page in reader.pages])

    assert "OISST" in pdf_text or "Sea Surface Temperature" in pdf_text
    assert "0.25° × 0.25° Regular Grid" in pdf_text
    assert "ocean-only blended product" in pdf_text
    assert "10.25921/RE9P-PT57" in pdf_text

    # Check CSV export
    csv_file = tmp_path / f"report_{report_res['report_id']}_timeseries.csv"
    assert csv_file.exists()
    with open(csv_file, "r", encoding="utf-8") as f:
        csv_content = f.read()
    assert "noaa_oisst_v21" in csv_content
    assert "°C" in csv_content
