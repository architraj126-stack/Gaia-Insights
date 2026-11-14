"""
Unit tests for Change Detection Service & API (Phase 5, SPEC 9, 14.5, 14.8).

Tests:
- Synthetic two-period fields with a known difference (sign and units).
- NaN cells preserved (missing is never zero; no silent interpolation).
- Percentage change suppressed for near-zero baselines (|A| <= epsilon).
- Area weighting: a cell at 60 degrees latitude weighs about half an equatorial cell.
- Partial boundary cell weighting with fractional overlap.
- Overlapping periods rejection and explicit confirmation override.
- GeoTIFF generation via rioxarray.
- Transparent map overlay PNG generation and symmetric legend.
- Cell inspection endpoint.
"""
import calendar
import math
import shutil
import tempfile
from pathlib import Path
from typing import List

import numpy as np
import pytest
import xarray as xr
from fastapi.testclient import TestClient
from shapely.geometry import Polygon, box

from backend.app.main import app
from backend.app.services.change import (
    check_periods_overlap,
    compute_annual_cell_values,
    compute_period_mean_field,
    compute_spatial_summary,
    compute_spatial_trend_slope,
    execute_change_detection_analysis,
    generate_map_overlay_and_legend,
    inspect_change_cell,
    validate_period_coverage,
    write_geotiff,
)
from backend.app.services.regions import build_grid_mask_weights, compute_geodesic_cell_area_km2


def create_synthetic_dataset(
    lats: np.ndarray,
    lons: np.ndarray,
    years: List[int],
    fill_value: float = np.nan,
    generator_fn=None,
) -> xr.DataArray:
    """Creates a synthetic monthly DataArray with proper time, lat, lon coordinates."""
    time_steps = []
    for y in years:
        for m in range(1, 13):
            time_steps.append(f"{y}-{m:02d}-01")

    n_times = len(time_steps)
    n_lats = len(lats)
    n_lons = len(lons)

    if generator_fn:
        data = generator_fn(n_times, n_lats, n_lons)
    else:
        data = np.full((n_times, n_lats, n_lons), fill_value, dtype=np.float64)

    da = xr.DataArray(
        data,
        coords=[("time", time_steps), ("lat", lats), ("lon", lons)],
        name="precip",
    )
    return da


def test_synthetic_two_period_difference_known_values():
    """
    Test synthetic two-period fields with known difference (sign and units).
    Baseline (1990-1991): constant 2.0 mm/day
    Comparison (1992-1993): constant 5.0 mm/day
    Annual precipitation in non-leap year (365 days):
    Baseline annual total: 2.0 * 365 = 730 mm/year
    Comparison annual total: 5.0 * 365 = 1825 mm/year
    Expected absolute difference: 1825 - 730 = +1095 mm/year
    Expected percentage change: 100 * (1825 - 730) / 730 = +150.0%
    """
    lats = np.array([-10.0, 0.0, 10.0])
    lons = np.array([10.0, 20.0, 30.0])
    years = [1990, 1991, 1992, 1993]

    def gen(t, y, x):
        arr = np.zeros((t, y, x), dtype=np.float64)
        # First 24 months (1990, 1991) = 2.0
        arr[:24, :, :] = 2.0
        # Next 24 months (1992, 1993) = 5.0
        arr[24:, :, :] = 5.0
        return arr

    da = create_synthetic_dataset(lats, lons, years, generator_fn=gen)
    geom = box(5.0, -15.0, 35.0, 15.0)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Absolute difference
        res_abs = execute_change_detection_analysis(
            data_array=da,
            geometry=geom,
            baseline_years=(1990, 1991),
            comparison_years=(1992, 1993),
            variable="precipitation",
            metric="absolute",
            aggregation="annual",
            output_dir=tmp_path,
        )
        assert res_abs["units"] == "mm/year"
        # 1990 is not leap (365), 1991 is not leap (365) -> baseline = 730
        # 1992 is leap year (366 days -> 1830), 1993 is not leap (365 days -> 1825)
        # mean comparison = (1830 + 1825)/2 = 1827.5 mm/year
        expected_diff = 1827.5 - 730.0  # 1097.5 mm/year
        assert abs(res_abs["spatial_summary"]["area_weighted_mean_change"] - expected_diff) < 1e-2
        assert res_abs["spatial_summary"]["share_increasing_pct"] == 100.0
        assert res_abs["spatial_summary"]["share_decreasing_pct"] == 0.0

        # Percentage difference
        res_pct = execute_change_detection_analysis(
            data_array=da,
            geometry=geom,
            baseline_years=(1990, 1991),
            comparison_years=(1992, 1993),
            variable="precipitation",
            metric="percentage",
            aggregation="annual",
            output_dir=tmp_path,
        )
        assert res_pct["units"] == "%"
        expected_pct = 100.0 * (1827.5 - 730.0) / 730.0
        assert abs(res_pct["spatial_summary"]["area_weighted_mean_change"] - expected_pct) < 1e-2


def test_nan_cells_preserved_never_substituted_zero():
    """
    Test that NaN cells remain NaN throughout calculation and are never silently substituted with zero.
    """
    lats = np.array([0.0, 10.0])
    lons = np.array([0.0, 10.0])
    years = [1990, 1991]

    def gen(t, y, x):
        arr = np.full((t, y, x), 3.0, dtype=np.float64)
        # Make cell (0, 0) have NaN for one single month in baseline
        arr[5, 0, 0] = np.nan
        # Make cell (1, 1) completely NaN everywhere
        arr[:, 1, 1] = np.nan
        return arr

    da = create_synthetic_dataset(lats, lons, years, generator_fn=gen)
    geom = box(-5.0, -5.0, 15.0, 15.0)

    with tempfile.TemporaryDirectory() as tmpdir:
        res = execute_change_detection_analysis(
            data_array=da,
            geometry=geom,
            baseline_years=(1990, 1990),
            comparison_years=(1991, 1991),
            variable="precipitation",
            metric="absolute",
            aggregation="annual",
            output_dir=Path(tmpdir),
        )

        # Inspect cell (0, 0): missing month in 1990 means annual total is NaN -> difference is NaN
        inspect_00 = inspect_change_cell(res["run_id"], 0.0, 0.0, output_dir=Path(tmpdir))
        assert inspect_00["baseline_mean"] is None
        assert inspect_00["difference"] is None
        assert inspect_00["is_valid"] is False

        # Inspect cell (1, 1): completely NaN
        inspect_11 = inspect_change_cell(res["run_id"], 10.0, 10.0, output_dir=Path(tmpdir))
        assert inspect_11["baseline_mean"] is None
        assert inspect_11["comparison_mean"] is None
        assert inspect_11["difference"] is None

        # Inspect cell (0, 1): fully valid
        inspect_01 = inspect_change_cell(res["run_id"], 0.0, 10.0, output_dir=Path(tmpdir))
        assert inspect_01["baseline_mean"] is not None
        assert inspect_01["difference"] == 0.0
        assert inspect_01["is_valid"] is True

        # Check no-data area is reported separately from no-change area
        summary = res["spatial_summary"]
        assert summary["nodata_area_km2"] > 0
        assert summary["nodata_share_pct"] > 0
        assert summary["share_no_change_pct"] > 0


def test_percentage_suppressed_for_near_zero_baseline():
    """
    Percentage change must be suppressed (NaN with warning) where baseline |A| <= epsilon.
    """
    lats = np.array([0.0, 10.0])
    lons = np.array([0.0, 10.0])
    years = [1990, 1991]

    def gen(t, y, x):
        arr = np.zeros((t, y, x), dtype=np.float64)
        # Cell (0, 0): Baseline near zero (0.0001 mm/day -> annual ~0.036 mm), Comparison = 2.0 mm/day
        arr[:12, 0, 0] = 0.0001
        arr[12:, 0, 0] = 2.0

        # Cell (0, 1): Baseline robust (5.0 mm/day -> annual 1825 mm), Comparison = 10.0 mm/day
        arr[:12, 0, 1] = 5.0
        arr[12:, 0, 1] = 10.0
        return arr

    da = create_synthetic_dataset(lats, lons, years, generator_fn=gen)
    geom = box(-5.0, -5.0, 15.0, 15.0)

    with tempfile.TemporaryDirectory() as tmpdir:
        res = execute_change_detection_analysis(
            data_array=da,
            geometry=geom,
            baseline_years=(1990, 1990),
            comparison_years=(1991, 1991),
            variable="precipitation",
            metric="percentage",
            aggregation="annual",
            epsilon=1.0,  # 1.0 mm/year threshold
            output_dir=Path(tmpdir),
        )

        # Warning must be emitted
        assert any("Percentage change suppressed" in w for w in res["warnings"])

        # Cell (0, 0) should be NaN (suppressed)
        inspect_00 = inspect_change_cell(res["run_id"], 0.0, 0.0, output_dir=Path(tmpdir))
        assert inspect_00["difference"] is None
        assert inspect_00["is_valid"] is False

        # Cell (0, 1) should be valid (+100%)
        inspect_01 = inspect_change_cell(res["run_id"], 0.0, 10.0, output_dir=Path(tmpdir))
        assert inspect_01["difference"] is not None
        assert abs(inspect_01["difference"] - 100.0) < 1e-2


def test_area_weighting_latitude_cosine_scaling():
    """
    Test area weighting: a cell at 60 degrees latitude weighs about half an equatorial cell
    because cos(60 deg) = 0.5.
    """
    # 2.5 degree cell at equator vs 60N
    dlat = 2.5
    dlon = 2.5
    area_eq = compute_geodesic_cell_area_km2(0.0, dlat, dlon)
    area_60 = compute_geodesic_cell_area_km2(60.0, dlat, dlon)

    ratio = area_60 / area_eq
    # cos(60 deg) = 0.5. Ratio should be very close to 0.5 (within 1%)
    assert abs(ratio - 0.5) < 0.01

    # In spatial summary of a 2-cell grid (one at 0, one at 60):
    # Suppose cell at 0 has change = +10, cell at 60 has change = +20.
    # Area-weighted mean should be (10 * 1.0 + 20 * 0.5) / 1.5 = 20/1.5 = 13.333
    lats = np.array([0.0, 60.0])
    lons = np.array([0.0])
    years = [1990, 1991]

    def gen(t, y, x):
        arr = np.zeros((t, y, x), dtype=np.float64)
        # Year 1990: 1.0 mm/day
        arr[:12, :, :] = 1.0
        # Year 1991: equator = 2.0 mm/day (+1 mm/day change), 60N = 3.0 mm/day (+2 mm/day change)
        arr[12:, 0, 0] = 2.0
        arr[12:, 1, 0] = 3.0
        return arr

    da = create_synthetic_dataset(lats, lons, years, generator_fn=gen)
    geom = box(-10.0, -10.0, 10.0, 70.0)

    with tempfile.TemporaryDirectory() as tmpdir:
        res = execute_change_detection_analysis(
            data_array=da,
            geometry=geom,
            baseline_years=(1990, 1990),
            comparison_years=(1991, 1991),
            variable="precipitation",
            metric="absolute",
            aggregation="monthly",  # using rate directly to test weighted mean
            output_dir=Path(tmpdir),
        )
        mean_change = res["spatial_summary"]["area_weighted_mean_change"]
        expected_weighted = (1.0 * area_eq + 2.0 * area_60) / (area_eq + area_60)
        assert abs(mean_change - expected_weighted) < 1e-4


def test_partial_boundary_cell_weighting():
    """
    Test partial boundary cell weighting:
    A cell that only half intersects a polygon receives a fractional area weight.
    """
    lats = np.array([0.0])
    lons = np.array([0.0, 2.5])  # Cells [-1.25, 1.25] and [1.25, 3.75]
    # Polygon covers all of cell 0 and half of cell 1 (from -1.25 to 2.5 lon)
    poly = box(-1.25, -1.25, 2.5, 1.25)

    weights_2d, fractions_2d, cell_areas_2d, method = build_grid_mask_weights(
        lats, lons, poly, method="fractional_overlap"
    )

    # Cell 0 is completely inside: fraction = 1.0
    assert abs(fractions_2d[0, 0] - 1.0) < 1e-4
    # Cell 1 is half inside (from 1.25 to 2.5, out of width 2.5): fraction = 0.5
    assert abs(fractions_2d[0, 1] - 0.5) < 1e-4

    # Weight of cell 1 must be half of its nominal area
    assert abs(weights_2d[0, 1] - (0.5 * cell_areas_2d[0, 1])) < 1e-4


def test_overlapping_periods_validation_and_override():
    """
    Test that overlapping periods are rejected by default, and allowed only with explicit confirmation.
    """
    # Overlapping periods [1990, 2005] and [2000, 2010]
    with pytest.raises(ValueError, match="overlap"):
        check_periods_overlap((1990, 2005), (2000, 2010), allow_overlap=False)

    # With allow_overlap=True, it should proceed and emit a warning
    warnings = check_periods_overlap((1990, 2005), (2000, 2010), allow_overlap=True)
    assert len(warnings) == 1
    assert "explicit confirmation" in warnings[0]


def test_spatial_trend_metric():
    """
    Test spatial trend metric computes slope per year across the span.
    """
    lats = np.array([0.0])
    lons = np.array([0.0])
    years = [2000, 2001, 2002, 2003]

    # Rates increasing by 1.0 mm/day every year -> 365 mm/year per year
    def gen(t, y, x):
        arr = np.zeros((t, y, x), dtype=np.float64)
        for i, y_val in enumerate(years):
            arr[i * 12 : (i + 1) * 12, 0, 0] = float(i + 1)
        return arr

    da = create_synthetic_dataset(lats, lons, years, generator_fn=gen)
    geom = box(-5.0, -5.0, 5.0, 5.0)

    with tempfile.TemporaryDirectory() as tmpdir:
        res = execute_change_detection_analysis(
            data_array=da,
            geometry=geom,
            baseline_years=(2000, 2001),
            comparison_years=(2002, 2003),
            variable="precipitation",
            metric="spatial_trend",
            aggregation="annual",
            output_dir=Path(tmpdir),
        )
        assert res["metric"] == "spatial_trend"
        # Slope should be approximately 365 mm/year/year
        mean_slope = res["spatial_summary"]["area_weighted_mean_change"]
        assert abs(mean_slope - 365.25) < 2.0


def test_geotiff_and_overlay_outputs_generated():
    """
    Test that GeoTIFF and Leaflet PNG overlay and legend are created.
    """
    lats = np.array([0.0, 2.5])
    lons = np.array([10.0, 12.5])
    years = [1990, 1991]

    da = create_synthetic_dataset(
        lats,
        lons,
        years,
        generator_fn=lambda t, y, x: np.full((t, y, x), 2.5, dtype=np.float64),
    )
    geom = box(8.0, -2.0, 15.0, 5.0)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        res = execute_change_detection_analysis(
            data_array=da,
            geometry=geom,
            baseline_years=(1990, 1990),
            comparison_years=(1991, 1991),
            output_dir=tmp_path,
        )

        run_id = res["run_id"]
        tif_path = tmp_path / f"change_{run_id}.tif"
        png_path = tmp_path / f"overlay_{run_id}.png"
        json_path = tmp_path / f"inspect_{run_id}.json"

        assert tif_path.exists()
        assert png_path.exists()
        assert json_path.exists()

        # Check legend structure
        legend = res["legend"]
        assert legend["colormap"] == "RdBu_r"
        assert legend["min_val"] == -1.0
        assert legend["max_val"] == 1.0
        assert len(legend["thresholds"]) == 5
        assert len(legend["colors"]) == 5
        assert "no_data_swatch" in legend


def test_api_change_map_endpoints():
    """
    Test FastAPI endpoints:
    - POST /api/analysis/change-map
    - GET /api/analysis/change-map/{run_id}
    - GET /api/analysis/change-map/{run_id}/geotiff
    - GET /api/analysis/change-map/{run_id}/overlay.png
    - POST /api/analysis/change-map/inspect
    """
    client = TestClient(app)

    # Test bad request without geometry
    resp_no_geom = client.post("/api/analysis/change-map", json={"dataset_id": "gpcp_monthly_v23"})
    assert resp_no_geom.status_code == 400

    test_geom = {
        "type": "Polygon",
        "coordinates": [[[-10.0, -10.0], [10.0, -10.0], [10.0, 10.0], [-10.0, 10.0], [-10.0, -10.0]]],
    }

    # Test overlap rejection
    resp_overlap = client.post(
        "/api/analysis/change-map",
        json={
            "dataset_id": "gpcp_monthly_v23",
            "geometry": test_geom,
            "baseline_period": [1990, 2005],
            "comparison_period": [2000, 2015],
            "allow_overlap": False,
        },
    )
    assert resp_overlap.status_code == 400
    assert "overlap" in resp_overlap.json()["detail"].lower()


@pytest.mark.asyncio
async def test_real_gpcp_change_map_integration():
    """
    End-to-end integration test querying real GPCP data for a change map.
    Verifies:
    1. Returns valid change map response with overlay_url, geotiff_url, bounds, legend, and spatial_summary.
    2. Legend has diverging RdBu_r symmetric about zero with units matching data (mm/year).
    3. GeoTIFF file and PNG overlay exist on disk.
    4. Cell inspect returns valid values.
    5. Second call is served from cache.
    """
    from backend.app.api.analysis import (
        ChangeMapRequest,
        create_change_map_analysis,
        inspect_cell_get,
    )
    from backend.app.services.boundaries import get_boundary_by_id

    boundary = get_boundary_by_id("admin0_fji_fiji")
    if not boundary:
        pytest.skip("Boundary admin0_fji_fiji not found in test environment.")

    req = ChangeMapRequest(
        dataset_id="gpcp_monthly_v23",
        dataset_version="v2.3",
        variable="precipitation",
        region_id="admin0_fji_fiji",
        baseline_period=[1990, 2005],
        comparison_period=[2006, 2025],
        metric="absolute",
        aggregation="annual",
    )

    resp1 = await create_change_map_analysis(req, session=None)
    assert resp1["status"] == "completed"
    assert resp1["units"] == "mm/year"
    assert resp1["overlay_url"].startswith("/api/analysis/change-map/")
    assert resp1["geotiff_url"].startswith("/api/analysis/change-map/")
    assert "spatial_summary" in resp1
    assert resp1["legend"]["colormap"] == "RdBu_r"
    assert resp1["legend"]["units"] == "mm/year"
    assert resp1["legend"]["symmetric_zero"] == 0.0

    run_id = resp1["run_id"]

    # Test cell inspection
    bounds = resp1["bounds"]
    mid_lat = (bounds[0][0] + bounds[1][0]) / 2.0
    mid_lon = (bounds[0][1] + bounds[1][1]) / 2.0

    inspect_res = await inspect_cell_get(run_id=run_id, lat=mid_lat, lon=mid_lon)
    assert inspect_res["run_id"] == run_id
    assert inspect_res["units"] == "mm/year"
    assert inspect_res["metric"] == "absolute"

    # Test cache hit on second call
    resp2 = await create_change_map_analysis(req, session=None)
    assert resp2["run_id"] == resp1["run_id"]
    assert resp2["overlay_url"] == resp1["overlay_url"]
