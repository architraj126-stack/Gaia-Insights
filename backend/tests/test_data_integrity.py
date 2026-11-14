"""
Data Integrity & Honesty Tests (SPEC 3.3, 6, 14.8, 15, AGENTS.md).

Tests:
1. A disjoint region returns 0 valid cells and status 'Unavailable'.
2. The four uningested datasets return 'Unavailable - real data not yet ingested'
   in catalogue, availability checks, and all analysis endpoints.
3. A grep check fails if any hardcoded date strings ("2026-10-01", [2006, 2025], "2025-12-01")
   reappear in backend application code.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

import numpy as np
import pytest
import xarray as xr
from fastapi.testclient import TestClient
from shapely.geometry import box

from backend.app.api.catalog import load_catalog_seed
from backend.app.main import app
from backend.app.services.availability import check_dataset_availability
from backend.app.services.regions import extract_regional_mean_timeseries


UNINGESTED_DATASET_IDS = [
    "merra2_monthly_ts",
    "noaa_oisst_v21",
    "gldas_noah025_m_v21",
    "merra2_monthly_qv2m",
]


def test_disjoint_region_returns_unavailable():
    """
    Requirement 3 & 7: A region disjoint from dataset extent (outside 1 grid cell buffer)
    must return 0 valid cells and status 'Unavailable', without nearest_cell_fallback.
    """
    # Create a synthetic regional DataArray covering [10, 20] lat, [10, 20] lon
    lats = np.arange(10.0, 20.0, 2.5)
    lons = np.arange(10.0, 20.0, 2.5)
    times = ["2020-01-01", "2020-02-01"]
    data = np.ones((len(times), len(lats), len(lons)), dtype=np.float32)

    da = xr.DataArray(
        data,
        coords={"time": times, "lat": lats, "lon": lons},
        dims=["time", "lat", "lon"],
    )

    # Disjoint geometry far away (e.g. lat [50, 60], lon [50, 60])
    disjoint_geom = box(50.0, 50.0, 60.0, 60.0)

    result = extract_regional_mean_timeseries(da, disjoint_geom)

    assert result["status"] == "Unavailable"
    assert result["intersecting_cell_count"] == 0
    assert result["total_region_area_km2"] == 0.0
    assert all(c == 0 for c in result["valid_cell_counts"])
    assert all(m is None for m in result["mean_values"])
    assert result["mask_method"] == "disjoint_unavailable"
    assert any("disjoint" in w.lower() for w in result.get("warnings", []))


def test_four_datasets_return_unavailable_until_real_data_exists():
    """
    Requirement 2 & 7: The 4 datasets must show 'Unavailable - real data not yet ingested'
    in catalog seed, availability, and all analysis endpoints.
    """
    # 1. Catalog seed
    variables = load_catalog_seed()
    datasets_by_id = {ds.id: ds for var in variables for ds in var.datasets}

    for ds_id in UNINGESTED_DATASET_IDS:
        assert ds_id in datasets_by_id, f"Dataset {ds_id} not found in catalog seed"
        ds = datasets_by_id[ds_id]
        assert ds.status == "Unavailable - real data not yet ingested", (
            f"Expected {ds_id} to be 'Unavailable - real data not yet ingested', got {ds.status}"
        )

    # 2. Availability endpoint / service
    for ds_id in UNINGESTED_DATASET_IDS:
        avail = check_dataset_availability(ds_id)
        assert avail["status"] == "Unavailable - real data not yet ingested", (
            f"Expected {ds_id} availability status to be 'Unavailable - real data not yet ingested', got {avail['status']}"
        )
        assert avail["cell_count"] == 0
        assert avail["spatial_coverage_percent"] == 0.0

    # 3. Analysis endpoints reject uningested datasets with HTTP 400
    client = TestClient(app)
    demo_geom = {
        "type": "Polygon",
        "coordinates": [[[15.0, 15.0], [20.0, 15.0], [20.0, 20.0], [15.0, 20.0], [15.0, 15.0]]],
    }

    for ds_id in UNINGESTED_DATASET_IDS:
        # Timeseries
        ts_resp = client.post(
            "/api/analysis/timeseries",
            json={
                "dataset_id": ds_id,
                "geometry": demo_geom,
                "variable": "temperature",
                "start_date": "2000-01-01",
                "end_date": "2024-12-01",
            },
        )
        assert ts_resp.status_code == 400
        assert "Unavailable - real data not yet ingested" in ts_resp.json()["detail"]

        # Change Map
        change_resp = client.post(
            "/api/analysis/change-map",
            json={
                "dataset_id": ds_id,
                "geometry": demo_geom,
                "variable": "temperature",
            },
        )
        assert change_resp.status_code == 400
        assert "Unavailable - real data not yet ingested" in change_resp.json()["detail"]

        # Significance
        sig_resp = client.post(
            "/api/analysis/significance",
            json={
                "dataset_id": ds_id,
                "geometry": demo_geom,
                "variable": "temperature",
            },
        )
        assert sig_resp.status_code == 400
        assert "Unavailable - real data not yet ingested" in sig_resp.json()["detail"]


def test_no_hardcoded_date_strings_grep():
    """
    Requirement 4 & 7: Grep test verifying that hardcoded date strings
    do not reappear in backend application code.
    """
    backend_app_dir = Path(__file__).resolve().parent.parent / "app"
    assert backend_app_dir.exists()

    forbidden_patterns = [
        re.compile(r'2026-10-01'),
        re.compile(r'2025-12-01'),
        re.compile(r'\[2006,\s*2025\]'),
        re.compile(r'\[1990,\s*2005\]'),
    ]

    violations: List[str] = []

    for py_file in backend_app_dir.rglob("*.py"):
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Ignore comments
            if stripped.startswith("#"):
                continue
            for pattern in forbidden_patterns:
                if pattern.search(line):
                    violations.append(f"{py_file.relative_to(backend_app_dir)}:{line_num} -> {line.strip()}")

    assert not violations, f"Hardcoded date strings found in backend/app:\n" + "\n".join(violations)
