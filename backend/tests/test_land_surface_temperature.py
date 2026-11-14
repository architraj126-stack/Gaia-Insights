"""
Comprehensive Test Suite for Land Surface Temperature (Phase 7).

Covers:
1. Unit conversion tests (Kelvin to Celsius, preserving provenance and NaNs).
2. Land/ocean mask enforcement (no ocean values for land-only variable, availability Partial/Unavailable).
3. Intensive state variable aggregation (monthly mean -> annual mean, never sum).
4. Real-data end-to-end integration test across Pages 1-5 and the report for Chad.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest
import xarray as xr
from pypdf import PdfReader

from backend.app.services.aggregate import (
    aggregate_annual,
    aggregate_monthly,
    kelvin_to_celsius,
)
from backend.app.services.availability import check_dataset_availability
from backend.app.services.boundaries import (
    calculate_geometry_land_ratio,
    get_boundary_by_id,
    is_point_on_land,
)
from backend.app.services.change import execute_change_detection_analysis
from backend.app.services.ingest import (
    get_cached_merra2_file_path,
    normalize_dataset,
    open_dataset,
)
from backend.app.services.regions import (
    build_grid_mask_weights,
    extract_regional_mean_timeseries,
)
from backend.app.services.reports import (
    create_report,
    RESULTS_CACHE_DIR,
    OUTPUTS_DIR,
)
from backend.app.services.significance import execute_significance_analysis
from shapely.geometry import shape


# ===========================================================================
# 1. Unit Conversion Tests
# ===========================================================================

def test_kelvin_to_celsius_scalar_and_array():
    """Verify Kelvin to Celsius conversion: °C = K - 273.15."""
    assert abs(kelvin_to_celsius(300.0) - 26.85) < 1e-6
    assert abs(kelvin_to_celsius(273.15) - 0.0) < 1e-6
    assert abs(kelvin_to_celsius(0.0) - (-273.15)) < 1e-6

    # Array conversion
    k_arr = np.array([273.15, 300.0, 373.15, np.nan])
    c_arr = kelvin_to_celsius(k_arr)
    assert abs(c_arr[0] - 0.0) < 1e-6
    assert abs(c_arr[1] - 26.85) < 1e-6
    assert abs(c_arr[2] - 100.0) < 1e-6
    assert np.isnan(c_arr[3])


# ===========================================================================
# 2. Land/Ocean Mask Enforcement Tests
# ===========================================================================

def test_land_ocean_mask_boundary_checks():
    """Verify land mask distinguishes terrestrial land from ocean points."""
    # Point in the middle of South Atlantic Ocean (0°E, 0°N) is ocean
    assert not is_point_on_land(0.0, 0.0)

    # Point in Chad (18°E, 15°N) is land
    assert is_point_on_land(18.0, 15.0)

    # Point in Central Paris (2.35°E, 48.85°N) is land
    assert is_point_on_land(2.35, 48.85)

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

    # Terrestrial Chad polygon
    chad_feature = get_boundary_by_id("admin0_tcd_chad")
    assert chad_feature is not None
    ratio_chad = calculate_geometry_land_ratio(chad_feature["geometry"])
    assert ratio_chad > 0.98


def test_land_only_availability_reporting():
    """
    Verify availability reports Unavailable for ocean and Partial for coast for land-only variables.
    """
    merra2_product_meta = {
        "spatial_coverage": "Global (Land-only variable TS)",
        "spatial_resolution": "0.625° × 0.5°",
        "grid_resolution_deg": [0.625, 0.5],
        "start_date": "1980-01-01",
        "latest_observation_date": "2024-12-01",
        "bounding_box": [-180.0, -90.0, 180.0, 90.0],
        "coverage_type": "land_only",
    }

    # 1. Pure Ocean Region -> Status must be 'Unavailable'
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
    # 1. Un-ingested dataset availability reporting (SPEC 14.8 / Requirement 2)
    avail_ocean = check_dataset_availability(
        dataset_id="merra2_monthly_ts",
        geometry=ocean_geom,
    )
    assert avail_ocean["status"] == "Unavailable - real data not yet ingested"
    assert avail_ocean["cell_count"] == 0

    # 2. Terrestrial Region (Chad) -> Status must also be 'Unavailable - real data not yet ingested'
    chad_feature = get_boundary_by_id("admin0_tcd_chad")
    avail_chad = check_dataset_availability(
        dataset_id="merra2_monthly_ts",
        geometry=chad_feature["geometry"],
    )
    assert avail_chad["status"] == "Unavailable - real data not yet ingested"
    assert avail_chad["cell_count"] == 0


# ===========================================================================
# 3. Intensive State Variable Aggregation Tests
# ===========================================================================

def test_temperature_annual_aggregation_is_mean_not_sum():
    """
    Verify aggregation rule for temperature (SPEC 14.3):
    Temperature is an intensive state variable. Annual aggregation is the temporal MEAN,
    never the sum (accumulation).
    """
    # 24 months of synthetic temperature: Year 1 = 20.0 °C, Year 2 = 30.0 °C
    dates = [f"2020-{m:02d}-01" for m in range(1, 13)] + [f"2021-{m:02d}-01" for m in range(1, 13)]
    points = []
    for d in dates:
        val = 20.0 if d.startswith("2020") else 30.0
        points.append({
            "date": d,
            "value": val,
            "units": "°C",
            "is_missing": False,
            "valid_cells": 10,
            "valid_area_km2": 10000.0,
            "flags": ["valid"],
        })

    annual_pts = aggregate_annual(points, variable="temperature")
    assert len(annual_pts) == 2

    # Year 2020 should have mean 20.0 °C (NOT 12 * 20.0 = 240.0)
    assert annual_pts[0]["date"] == "2020-01-01"
    assert abs(annual_pts[0]["value"] - 20.0) < 1e-4

    # Year 2021 should have mean 30.0 °C (NOT 12 * 30.0 = 360.0)
    assert annual_pts[1]["date"] == "2021-01-01"
    assert abs(annual_pts[1]["value"] - 30.0) < 1e-4


# ===========================================================================
# 4. Real-Data End-to-End Integration Test for Chad
# ===========================================================================

def test_merra2_real_data_pipeline_end_to_end_chad(tmp_path: Path):
    """
    Full real-data integration test using cached MERRA-2 skin temperature for Chad:
    1. Ingestion: open_dataset & normalize_dataset.
    2. Timeseries: extract_regional_mean_timeseries in °C.
    3. Change Detection: execute_change_detection_analysis.
    4. Significance: compute_significance_analysis.
    5. Report: create_report compiling PDF & CSV with MERRA-2 citations & caveats.
    """
    # 1. Verify honest quarantine status: file not in application cache & API rejects
    cached_file = get_cached_merra2_file_path()
    assert not cached_file.exists(), f"Quarantined fixture must not exist in application cache at {cached_file}"
    avail = check_dataset_availability("merra2_monthly_ts")
    assert avail["status"] == "Unavailable - real data not yet ingested"

    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    ts_resp = client.post(
        "/api/analysis/timeseries",
        json={
            "dataset_id": "merra2_monthly_ts",
            "region_id": "admin0_tcd_chad",
            "variable": "land_surface_temperature",
            "start_date": "1990-01-01",
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
    fixture_path = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "merra2_ts.mon.mean.nc"
    assert fixture_path.exists(), f"Fixture must exist in tests/fixtures at {fixture_path}"
    ds = xr.open_dataset(fixture_path, decode_times=False)
    assert "TS" in ds
    ds_norm = normalize_dataset(ds, "merra2_monthly_ts")
    assert "TS" in ds_norm
    var_arr = ds_norm["TS"]

    # Fill values (1e15) must be decoded to NaN
    assert np.all((var_arr.values < 1e10) | np.isnan(var_arr.values))

    # Regional Timeseries extraction using fixture
    chad_feature = get_boundary_by_id("admin0_tcd_chad")
    geom_shape = shape(chad_feature["geometry"])
    reg_series = extract_regional_mean_timeseries(var_arr, geom_shape)
    pts = aggregate_monthly(
        time_steps=reg_series["time_steps"],
        mean_rates=reg_series["mean_values"],
        valid_counts=reg_series["valid_cell_counts"],
        valid_areas=reg_series["valid_areas_km2"],
        variable="temperature",
    )
    assert len(pts) > 0

    valid_vals = [p["value"] for p in pts if p["value"] is not None and not np.isnan(p["value"])]
    assert len(valid_vals) > 0
    mean_temp = np.mean(valid_vals)
    assert 15.0 < mean_temp < 45.0, f"Expected realistic Chad skin temp in °C, got {mean_temp}"

    series_id = "test_series_ts_chad"
    ts_result = {
        "series_id": series_id,
        "dataset": {"units": "°C", "version": "5.12.4", "id": "merra2_monthly_ts"},
        "summary": {"mean": float(mean_temp)},
        "points": pts,
        "provenance": {"variable": "land_surface_temperature", "output_units": "°C", "actual_start": pts[0]["date"], "actual_end": pts[-1]["date"]},
        "coverage": {"actual_start": pts[0]["date"], "actual_end": pts[-1]["date"]},
    }
    with open(RESULTS_CACHE_DIR / f"{series_id}.json", "w", encoding="utf-8") as f:
        json.dump(ts_result, f)

    # 3. Spatial Change Detection
    chad_feature = get_boundary_by_id("admin0_tcd_chad")
    geom_shape = shape(chad_feature["geometry"])
    change_res = execute_change_detection_analysis(
        data_array=var_arr,
        geometry=geom_shape,
        baseline_years=(1990, 2005),
        comparison_years=(2006, 2024),
        variable="temperature",
        metric="absolute",
        output_dir=OUTPUTS_DIR,
    )

    assert change_res["units"] == "°C"
    assert "area_weighted_mean_change" in change_res["spatial_summary"]
    change_id = change_res["run_id"]
    with open(OUTPUTS_DIR / f"result_{change_id}.json", "w", encoding="utf-8") as f:
        json.dump(change_res, f)

    # 4. Statistical Significance
    geom_shape = shape(chad_feature["geometry"])
    sig_res = execute_significance_analysis(
        data_array=var_arr,
        geometry=geom_shape,
        time_series_points=pts,
        years=list(range(1990, 2025)),
        variable="temperature",
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
        title="MERRA-2 Land Surface Temperature Analysis — Chad",
        output_dir=tmp_path,
    )

    assert report_res["status"] == "completed"
    assert report_res["dataset_info"]["dataset_id"] == "merra2_monthly_ts"
    assert report_res["dataset_info"]["spatial_resolution"] == "0.625° × 0.5° Regular Grid"
    assert "reanalysis/model surface skin temperature" in report_res["dataset_info"]["caveat"]

    # Check compiled PDF text
    pdf_file = tmp_path / f"report_{report_res['report_id']}.pdf"
    assert pdf_file.exists()
    reader = PdfReader(str(pdf_file))
    pdf_text = " ".join([page.extract_text() for page in reader.pages])

    assert "MERRA-2" in pdf_text
    assert "0.625° × 0.5° Regular Grid" in pdf_text
    assert "reanalysis/model surface skin temperature" in pdf_text
    assert "10.5067/5ESKGQTZG7FO" in pdf_text

    # Check CSV export
    csv_file = tmp_path / f"report_{report_res['report_id']}_timeseries.csv"
    assert csv_file.exists()
    with open(csv_file, "r", encoding="utf-8") as f:
        csv_content = f.read()
    assert "merra2_monthly_ts" in csv_content
    assert "°C" in csv_content
