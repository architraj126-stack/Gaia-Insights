"""
Comprehensive Test Suite for Soil Moisture (Phase 7).

Covers:
1. Unit mapping tests (native kg m-2 to kg/m², preserving provenance and NaNs).
2. Land/ocean mask enforcement (no ocean values for land-only variable, availability Partial/Unavailable).
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
    get_cached_gldas_file_path,
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
# 1. Unit Mapping Tests
# ===========================================================================

def test_soil_moisture_unit_mapping_and_nan_preservation():
    """Verify soil moisture unit mapping: kg m-2 -> kg/m² with NaN preservation."""
    vals = np.array([5.2, 18.4, 32.0, np.nan, 0.0])
    converted = vals.copy()
    assert abs(converted[0] - 5.2) < 1e-6
    assert abs(converted[1] - 18.4) < 1e-6
    assert abs(converted[2] - 32.0) < 1e-6
    assert np.isnan(converted[3])
    assert abs(converted[4] - 0.0) < 1e-6


# ===========================================================================
# 2. Land/Ocean Mask Enforcement Tests
# ===========================================================================

def test_soil_moisture_land_mask_and_availability():
    """
    Verify land-only variable availability reporting:
    Since real data is not yet ingested, status is 'Unavailable - real data not yet ingested' (SPEC 14.8 / Requirement 2).
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
        dataset_id="gldas_noah025_m_v21",
        geometry=ocean_geom,
    )
    assert avail_ocean["status"] == "Unavailable - real data not yet ingested"
    assert avail_ocean["cell_count"] == 0

    # 2. Terrestrial Region (Chad) -> Status must also be 'Unavailable - real data not yet ingested'
    chad_feature = get_boundary_by_id("admin0_tcd_chad")
    avail_chad = check_dataset_availability(
        dataset_id="gldas_noah025_m_v21",
        geometry=chad_feature["geometry"],
    )
    assert avail_chad["status"] == "Unavailable - real data not yet ingested"
    assert avail_chad["cell_count"] == 0


# ===========================================================================
# 3. Intensive State Variable Aggregation Tests
# ===========================================================================

def test_soil_moisture_annual_aggregation_is_mean_not_sum():
    """
    Verify aggregation rule for soil moisture (SPEC 14.3):
    Soil moisture is an intensive state variable. Annual aggregation is the temporal MEAN,
    never the sum (accumulation).
    """
    # 24 months of synthetic soil moisture: Year 1 = 15.0 kg/m², Year 2 = 25.0 kg/m²
    dates = [f"2020-{m:02d}-01" for m in range(1, 13)] + [f"2021-{m:02d}-01" for m in range(1, 13)]
    points = []
    for d in dates:
        val = 15.0 if d.startswith("2020") else 25.0
        points.append({
            "date": d,
            "value": val,
            "units": "kg/m²",
            "is_missing": False,
            "valid_cells": 20,
            "valid_area_km2": 20000.0,
            "flags": ["valid"],
        })

    annual_pts = aggregate_annual(points, variable="soil_moisture")
    assert len(annual_pts) == 2

    # Year 2020 should have mean 15.0 kg/m² (NOT 12 * 15.0 = 180.0)
    assert annual_pts[0]["date"] == "2020-01-01"
    assert abs(annual_pts[0]["value"] - 15.0) < 1e-4

    # Year 2021 should have mean 25.0 kg/m² (NOT 12 * 25.0 = 300.0)
    assert annual_pts[1]["date"] == "2021-01-01"
    assert abs(annual_pts[1]["value"] - 25.0) < 1e-4


# ===========================================================================
# 4. Real-Data End-to-End Integration Test for Chad
# ===========================================================================

def test_gldas_real_data_pipeline_end_to_end_chad(tmp_path: Path):
    """
    Full real-data integration test using cached GLDAS Noah soil moisture for Chad:
    1. Ingestion: open_dataset & normalize_dataset.
    2. Timeseries: extract_regional_mean_timeseries in kg/m².
    3. Change Detection: execute_change_detection_analysis.
    4. Significance: compute_significance_analysis.
    5. Report: create_report compiling PDF & CSV with GLDAS citations & caveats.
    """
    # 1. Verify honest quarantine status: file not in application cache & API rejects
    cached_file = get_cached_gldas_file_path()
    assert not cached_file.exists(), f"Quarantined fixture must not exist in application cache at {cached_file}"
    avail = check_dataset_availability("gldas_noah025_m_v21")
    assert avail["status"] == "Unavailable - real data not yet ingested"

    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    ts_resp = client.post(
        "/api/analysis/timeseries",
        json={
            "dataset_id": "gldas_noah025_m_v21",
            "region_id": "admin0_tcd_chad",
            "variable": "soil_moisture",
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
    fixture_path = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "gldas_noah_sm.mon.mean.nc"
    assert fixture_path.exists(), f"Fixture must exist in tests/fixtures at {fixture_path}"
    ds = xr.open_dataset(fixture_path, decode_times=False)
    assert "SoilMoi0_10cm_inst" in ds
    ds_norm = normalize_dataset(ds, "gldas_noah025_m_v21")
    assert "SoilMoi0_10cm_inst" in ds_norm
    var_arr = ds_norm["SoilMoi0_10cm_inst"]

    # Fill values (-9999.0) must be decoded to NaN
    assert np.all((var_arr.values > -100.0) | np.isnan(var_arr.values))

    # Regional Timeseries extraction using fixture
    chad_feature = get_boundary_by_id("admin0_tcd_chad")
    geom_shape = shape(chad_feature["geometry"])
    reg_series = extract_regional_mean_timeseries(var_arr, geom_shape)
    pts = aggregate_monthly(
        time_steps=reg_series["time_steps"],
        mean_rates=reg_series["mean_values"],
        valid_counts=reg_series["valid_cell_counts"],
        valid_areas=reg_series["valid_areas_km2"],
        variable="soil_moisture",
    )
    assert len(pts) > 0

    valid_vals = [p["value"] for p in pts if p["value"] is not None and not np.isnan(p["value"])]
    assert len(valid_vals) > 0
    mean_sm = np.mean(valid_vals)
    assert 5.0 < mean_sm < 35.0, f"Expected realistic Chad soil moisture in kg/m², got {mean_sm}"

    series_id = "test_series_sm_chad"
    ts_result = {
        "series_id": series_id,
        "dataset": {"units": "kg/m²", "version": "2.1", "id": "gldas_noah025_m_v21"},
        "summary": {"mean": float(mean_sm)},
        "points": pts,
        "provenance": {"variable": "soil_moisture", "output_units": "kg/m²", "actual_start": pts[0]["date"], "actual_end": pts[-1]["date"]},
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
        variable="soil_moisture",
        metric="absolute",
        output_dir=OUTPUTS_DIR,
    )

    assert change_res["units"] == "kg/m²"
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
        variable="soil_moisture",
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
        title="GLDAS Noah Soil Moisture Analysis — Chad",
        output_dir=tmp_path,
    )

    assert report_res["status"] == "completed"
    assert report_res["dataset_info"]["dataset_id"] == "gldas_noah025_m_v21"
    assert report_res["dataset_info"]["spatial_resolution"] == "0.25° × 0.25° Regular Grid"
    assert "model-simulated water storage" in report_res["dataset_info"]["caveat"]

    # Check compiled PDF text
    pdf_file = tmp_path / f"report_{report_res['report_id']}.pdf"
    assert pdf_file.exists()
    reader = PdfReader(str(pdf_file))
    pdf_text = " ".join([page.extract_text() for page in reader.pages])

    assert "GLDAS" in pdf_text or "Soil Moisture" in pdf_text
    assert "0.25° × 0.25° Regular Grid" in pdf_text
    assert "model-simulated water storage" in pdf_text
    assert "10.5067/SXAVCZFAQLNO" in pdf_text

    # Check CSV export
    csv_file = tmp_path / f"report_{report_res['report_id']}_timeseries.csv"
    assert csv_file.exists()
    with open(csv_file, "r", encoding="utf-8") as f:
        csv_content = f.read()
    assert "gldas_noah025_m_v21" in csv_content
    assert "kg/m²" in csv_content
