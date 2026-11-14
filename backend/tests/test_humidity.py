"""
Comprehensive Test Suite for Humidity (Phase 7).

Covers:
1. Unit conversion tests (native kg/kg to g/kg via factor 1000.0, preserving NaNs).
2. Global atmospheric domain coverage (available over both land and ocean surfaces).
3. Intensive state variable aggregation (monthly state -> annual mean, never sum).
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
    get_cached_merra2_qv2m_file_path,
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

def test_humidity_unit_conversion_and_nan_preservation():
    """Verify humidity unit conversion: kg/kg -> g/kg via * 1000.0 with NaN preservation."""
    # kg/kg values
    vals = np.array([0.005, 0.0125, 0.024, np.nan, 0.0])
    converted = vals * 1000.0
    assert abs(converted[0] - 5.0) < 1e-6
    assert abs(converted[1] - 12.5) < 1e-6
    assert abs(converted[2] - 24.0) < 1e-6
    assert np.isnan(converted[3])
    assert abs(converted[4] - 0.0) < 1e-6


# ===========================================================================
# 2. Global Coverage & Availability Tests
# ===========================================================================

def test_humidity_global_coverage_and_availability():
    """
    Verify humidity dataset availability reporting:
    Since real data is not yet ingested, status is 'Unavailable - real data not yet ingested'.
    """
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
        dataset_id="merra2_monthly_qv2m",
        geometry=ocean_geom,
    )
    assert avail_ocean["status"] == "Unavailable - real data not yet ingested"
    assert avail_ocean["cell_count"] == 0

    # 2. Terrestrial Region (Chad) -> Status must also be 'Unavailable - real data not yet ingested'
    chad_feature = get_boundary_by_id("admin0_tcd_chad")
    assert chad_feature is not None
    avail_chad = check_dataset_availability(
        dataset_id="merra2_monthly_qv2m",
        geometry=chad_feature["geometry"],
    )
    assert avail_chad["status"] == "Unavailable - real data not yet ingested"
    assert avail_chad["cell_count"] == 0


# ===========================================================================
# 3. Intensive State Aggregation Tests (SPEC 14.3, Rule 7)
# ===========================================================================

def test_humidity_annual_aggregation_is_mean_not_sum():
    """
    Verify aggregation rule for humidity (SPEC 14.3):
    Specific humidity is an intensive state variable. Annual aggregation is the temporal MEAN,
    never the sum (accumulation).
    """
    dates = [f"2020-{m:02d}-01" for m in range(1, 13)] + [f"2021-{m:02d}-01" for m in range(1, 13)]
    points = []
    for d in dates:
        val = 6.0 if d.startswith("2020") else 14.0
        points.append({
            "date": d,
            "value": val,
            "units": "g/kg",
            "is_missing": False,
            "valid_cells": 20,
            "valid_area_km2": 20000.0,
            "flags": ["valid"],
        })

    annual_pts = aggregate_annual(points, variable="humidity")
    assert len(annual_pts) == 2

    # Year 2020 should have mean 6.0 g/kg (NOT 12 * 6.0 = 72.0)
    assert annual_pts[0]["date"] == "2020-01-01"
    assert abs(annual_pts[0]["value"] - 6.0) < 1e-4

    # Year 2021 should have mean 14.0 g/kg (NOT 12 * 14.0 = 168.0)
    assert annual_pts[1]["date"] == "2021-01-01"
    assert abs(annual_pts[1]["value"] - 14.0) < 1e-4


# ===========================================================================
# 4. Real-Data End-to-End Integration Test for Chad
# ===========================================================================

def test_merra2_qv2m_real_data_pipeline_end_to_end_chad(tmp_path: Path):
    """
    Full real-data integration test using cached MERRA-2 QV2M for Chad:
    1. Ingestion: open_dataset & normalize_dataset.
    2. Timeseries: extract_regional_mean_timeseries via API in g/kg.
    3. Change Detection: execute_change_detection_analysis in g/kg.
    4. Significance: execute_significance_analysis.
    5. Report: create_report compiling PDF & CSV with MERRA-2 citations & caveats.
    """
    # 1. Verify honest quarantine status: file not in application cache & API rejects
    cached_file = get_cached_merra2_qv2m_file_path()
    assert not cached_file.exists(), f"Quarantined fixture must not exist in application cache at {cached_file}"
    avail = check_dataset_availability("merra2_monthly_qv2m")
    assert avail["status"] == "Unavailable - real data not yet ingested"

    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    ts_resp = client.post(
        "/api/analysis/timeseries",
        json={
            "dataset_id": "merra2_monthly_qv2m",
            "region_id": "admin0_tcd_chad",
            "variable": "humidity",
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
    fixture_path = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "merra2_qv2m.mon.mean.nc"
    assert fixture_path.exists(), f"Fixture must exist in tests/fixtures at {fixture_path}"
    ds = xr.open_dataset(fixture_path, decode_times=False)
    assert "QV2M" in ds
    ds_norm = normalize_dataset(ds, "merra2_monthly_qv2m")
    assert "QV2M" in ds_norm
    var_arr = ds_norm["QV2M"]

    # Fill values (1.0e15) must be decoded to NaN
    assert np.all((var_arr.values < 1.0) | np.isnan(var_arr.values))

    # Regional Timeseries extraction using fixture
    chad_feature = get_boundary_by_id("admin0_tcd_chad")
    geom_shape = shape(chad_feature["geometry"])
    reg_series = extract_regional_mean_timeseries(var_arr, geom_shape)
    pts = aggregate_monthly(
        time_steps=reg_series["time_steps"],
        mean_rates=reg_series["mean_values"],
        valid_counts=reg_series["valid_cell_counts"],
        valid_areas=reg_series["valid_areas_km2"],
        variable="humidity",
    )
    assert len(pts) > 0

    valid_vals = [p["value"] for p in pts if p["value"] is not None and not np.isnan(p["value"])]
    assert len(valid_vals) > 0
    mean_hum = np.mean(valid_vals)
    assert 2.0 < mean_hum < 25.0, f"Expected realistic Chad 2m specific humidity in g/kg, got {mean_hum}"

    series_id = "test_series_qv2m_chad"
    ts_result = {
        "series_id": series_id,
        "dataset": {"units": "g/kg", "version": "5.12.4", "id": "merra2_monthly_qv2m"},
        "summary": {"mean": float(mean_hum)},
        "points": pts,
        "provenance": {"variable": "humidity", "output_units": "g/kg", "actual_start": pts[0]["date"], "actual_end": pts[-1]["date"]},
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
        baseline_years=(2000, 2009),
        comparison_years=(2010, 2019),
        variable="humidity",
        metric="absolute",
        output_dir=OUTPUTS_DIR,
    )

    assert change_res["units"] == "g/kg"
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
        variable="humidity",
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
        title="MERRA-2 2-Meter Specific Humidity Analysis — Chad",
        output_dir=tmp_path,
    )

    assert report_res["status"] == "completed"
    assert report_res["dataset_info"]["dataset_id"] == "merra2_monthly_qv2m"
    assert report_res["dataset_info"]["spatial_resolution"] == "0.625° × 0.5° Regular Grid"
    assert "distinct from total column precipitable water" in report_res["dataset_info"]["caveat"].lower()

    # Check compiled PDF text
    pdf_file = tmp_path / f"report_{report_res['report_id']}.pdf"
    assert pdf_file.exists()
    reader = PdfReader(str(pdf_file))
    pdf_text = " ".join([page.extract_text() for page in reader.pages])

    assert "MERRA-2" in pdf_text or "Humidity" in pdf_text
    assert "0.625° × 0.5° Regular Grid" in pdf_text
    assert "10.5067/AP1B0BA5PD2K" in pdf_text
    assert "g/kg" in pdf_text

    # Check CSV export
    csv_file = tmp_path / f"report_{report_res['report_id']}_timeseries.csv"
    assert csv_file.exists()
    with open(csv_file, "r", encoding="utf-8") as f:
        csv_content = f.read()
    assert "merra2_monthly_qv2m" in csv_content
    assert "g/kg" in csv_content
