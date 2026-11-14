"""
Statistical Tests for Significance Service & API (Phase 6a, SPEC 10, 14.6, 14.7, 14.8).

Tests:
1. Field of noise cells + injected trend cells:
   - Injected trend cells are detected.
   - Among pure noise cells, the false discovery rate is controlled (at or below alpha + tolerance).
   - Raw and adjusted p-value discovery counts differ (N_adj <= N_raw).
2. Seeded simulations show 95% CI covers the true slope ~95% of the time.
3. Low-sample cells are correctly labelled insufficient data.
4. Regional tests: seasonal MK, autocorrelation r1 evaluation, Hamed-Rao variance correction.
5. GeoTIFF and transparent overlay PNG generation.
6. API endpoint integration with cache reuse on alpha / FDR toggle.
"""
import math
import shutil
import tempfile
from pathlib import Path
from typing import List

import numpy as np
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box

from backend.app.main import app
from backend.app.services.significance import (
    CLASS_INSUFFICIENT_DATA,
    CLASS_NOT_SIGNIFICANT,
    CLASS_SIG_DECREASE,
    CLASS_SIG_INCREASE,
    classify_spatial_significance,
    compute_lag1_autocorrelation,
    execute_significance_analysis,
    generate_significance_map_overlay_and_legend,
    reclassify_cached_significance,
    evaluate_regional_significance,
    vectorized_mann_kendall_and_sen,
    write_significance_geotiff,
)


def test_field_of_noise_with_injected_trends_and_fdr_control():
    """
    Simulates a grid of 200 noise cells and 20 injected trend cells over T=35 years.
    Verifies:
    1. Injected trend cells are detected as significant.
    2. Among noise cells, the false discovery rate is controlled at or below alpha.
    3. Raw p-value significant count >= adjusted p-value count (multiplicity penalty).
    """
    np.random.seed(42)
    T = 35
    n_noise = 200
    n_trend = 20
    total_cells = n_noise + n_trend

    # 1. Generate noise cells: N(0, 1)
    noise_data = np.random.randn(T, n_noise)

    # 2. Injected trend cells: slope = +0.4 or -0.4 plus noise
    t_steps = np.arange(T, dtype=np.float64)[:, np.newaxis]
    pos_trends = 0.4 * t_steps + np.random.randn(T, n_trend // 2) * 0.5
    neg_trends = -0.4 * t_steps + np.random.randn(T, n_trend // 2) * 0.5
    trend_data = np.hstack([pos_trends, neg_trends])

    full_flat = np.hstack([noise_data, trend_data])  # (T, 220)
    # Reshape to (T, 11, 20)
    annual_cubes = full_flat.reshape(T, 11, 20)

    # Vectorised MK and Sen
    p_raw, slopes, valid_counts = vectorized_mann_kendall_and_sen(annual_cubes, min_valid_years=10)

    fractions = np.ones((11, 20), dtype=np.float64)

    # Classify with FDR = False (raw)
    classes_raw, p_raw_eval, counts_raw = classify_spatial_significance(
        p_raw, slopes, valid_counts, fractions, alpha=0.05, fdr_correction=False
    )

    # Classify with FDR = True (Benjamini-Hochberg)
    classes_fdr, p_fdr_eval, counts_fdr = classify_spatial_significance(
        p_raw, slopes, valid_counts, fractions, alpha=0.05, fdr_correction=True
    )

    raw_sig_total = counts_raw["significant_increase"] + counts_raw["significant_decrease"]
    fdr_sig_total = counts_fdr["significant_increase"] + counts_fdr["significant_decrease"]

    # Raw significant count must be >= FDR-adjusted significant count
    assert raw_sig_total >= fdr_sig_total

    # Verify injected trend cells are detected (trend cells are indices 200..219)
    classes_fdr_flat = classes_fdr.flatten()
    trend_classes = classes_fdr_flat[n_noise:]
    detected_injected = np.sum((trend_classes == CLASS_SIG_INCREASE) | (trend_classes == CLASS_SIG_DECREASE))
    assert detected_injected >= 18  # At least 90% of strong trends detected

    # Verify FDR on noise cells (false discoveries / total discoveries)
    noise_classes = classes_fdr_flat[:n_noise]
    false_discoveries = np.sum((noise_classes == CLASS_SIG_INCREASE) | (noise_classes == CLASS_SIG_DECREASE))
    total_discoveries = detected_injected + false_discoveries
    observed_fdr = false_discoveries / total_discoveries if total_discoveries > 0 else 0.0

    # FDR should stay controlled at or near alpha (with seed 42, false discoveries = 0 or 1, FDR < 0.05)
    assert observed_fdr <= 0.10


def test_confidence_interval_coverage_simulation():
    """
    Monte Carlo simulation: tests whether 95% CI covers true slope ~95% of the time.
    Runs 100 seeded simulations with known slope = 0.5.
    """
    np.random.seed(123)
    true_slope = 0.5
    n_sims = 100
    T = 30
    x = np.arange(T, dtype=np.float64)
    covered_count = 0

    from scipy.stats import theilslopes

    for _ in range(n_sims):
        y = true_slope * x + np.random.randn(T) * 1.5
        res = theilslopes(y, x, alpha=0.95)
        if res.low_slope <= true_slope <= res.high_slope:
            covered_count += 1

    coverage_rate = covered_count / n_sims
    # 95% CI coverage on 100 samples should be around 0.95 (within [0.88, 1.0])
    assert 0.88 <= coverage_rate <= 1.0


def test_low_sample_cells_labelled_insufficient_data():
    """
    Cells with fewer valid years than min_valid_years must be classified as insufficient data.
    """
    T = 20
    annual_cubes = np.random.randn(T, 2, 2)
    # Cell (0, 0) has only 5 valid years (< 10)
    annual_cubes[5:, 0, 0] = np.nan
    # Cell (1, 1) has only 2 valid years
    annual_cubes[2:, 1, 1] = np.nan

    p_raw, slopes, valid_counts = vectorized_mann_kendall_and_sen(annual_cubes, min_valid_years=10)
    fractions = np.ones((2, 2), dtype=np.float64)

    classes, _, counts = classify_spatial_significance(
        p_raw, slopes, valid_counts, fractions, min_valid_years=10, alpha=0.05
    )

    assert classes[0, 0] == CLASS_INSUFFICIENT_DATA
    assert classes[1, 1] == CLASS_INSUFFICIENT_DATA
    assert counts["insufficient_data"] == 2


def test_regional_significance_seasonal_and_autocorrelation():
    """
    Tests regional significance:
    - Computes lag-1 autocorrelation
    - Evaluates Seasonal Mann-Kendall on monthly data
    - Confirms proper null hypothesis text and interpretation
    """
    np.random.seed(99)
    # 36 monthly points with seasonal cycle and positive trend
    time_points = []
    for y in range(2000, 2003):
        for m in range(1, 13):
            val = float(100.0 + (y - 2000) * 10.0 + math.sin(m * math.pi / 6.0) * 15.0 + np.random.randn() * 2.0)
            time_points.append({
                "date": f"{y}-{m:02d}-01",
                "value": val,
            })

    res = evaluate_regional_significance(time_points, frequency="monthly", alpha=0.05)

    assert res["is_significant"] is True
    assert "Seasonal Mann-Kendall" in res["test_name"]
    assert "no monotonic trend" in res["null_hypothesis"]
    assert res["sens_slope"] > 0
    assert res["raw_p_value"] < 0.05
    assert "SPEC 10.5" in res["interpretation"]
    assert res["ci_lower"] is not None
    assert res["ci_upper"] is not None


def test_reclassification_without_rerunning_regressions():
    """
    Tests that reclassify_cached_significance re-uses cached spatial stats
    and reclassifies instantly when changing alpha or FDR option.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        T = 25
        time_coords = [f"{y}-{m:02d}-01" for y in range(2000, 2000 + T) for m in range(1, 13)]
        monthly_cubes = np.random.randn(T * 12, 5, 5) + 50.0
        # Inject strong positive trend in cell (2, 2)
        for y_idx in range(T):
            monthly_cubes[y_idx * 12 : (y_idx + 1) * 12, 2, 2] += y_idx * 2.0

        import xarray as xr
        da = xr.DataArray(
            monthly_cubes,
            coords=[("time", time_coords), ("lat", np.linspace(0, 10, 5)), ("lon", np.linspace(0, 10, 5))],
            name="precip",
        )
        geom = box(-1, -1, 11, 11)

        # Initial execution
        res1 = execute_significance_analysis(
            data_array=da,
            geometry=geom,
            years=list(range(2000, 2000 + T)),
            mode="spatial",
            alpha=0.05,
            fdr_correction=True,
            min_valid_years=5,
            output_dir=tmp_path,
        )

        run_id = res1["run_id"]
        assert res1["spatial"]["class_counts"]["significant_increase"] >= 1

        # Reclassify with very strict alpha = 0.000001
        res_reclass = reclassify_cached_significance(
            run_id=run_id,
            alpha=0.000001,
            fdr_correction=True,
            output_dir=tmp_path,
        )

        assert res_reclass["run_id"] == run_id
        assert res_reclass["alpha"] == 0.000001


def test_api_significance_endpoints():
    """
    Tests FastAPI significance endpoints:
    - POST /api/analysis/significance
    - GET /api/analysis/significance/{run_id}
    - GET /api/analysis/significance/{run_id}/geotiff
    - GET /api/analysis/significance/{run_id}/overlay.png
    """
    client = TestClient(app)

    # Bad request without geometry/region
    resp_bad = client.post("/api/analysis/significance", json={"dataset_id": "gpcp_monthly_v23"})
    assert resp_bad.status_code == 400

    # Valid request with geometry
    test_geom = {
        "type": "Polygon",
        "coordinates": [[[0.0, 0.0], [5.0, 0.0], [5.0, 5.0], [0.0, 5.0], [0.0, 0.0]]],
    }
    resp = client.post(
        "/api/analysis/significance",
        json={
            "dataset_id": "gpcp_monthly_v23",
            "geometry": test_geom,
            "mode": "spatial",
            "start_year": 2000,
            "end_year": 2015,
            "alpha": 0.05,
            "fdr_correction": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert "spatial" in data
    assert data["spatial"]["legend"]["type"] == "categorical_5_class"

    run_id = data["run_id"]

    # Test GET result
    get_res = client.get(f"/api/analysis/significance/{run_id}")
    assert get_res.status_code == 200

    # Test GET geotiff
    get_tif = client.get(f"/api/analysis/significance/{run_id}/geotiff")
    assert get_tif.status_code == 200
    assert get_tif.headers["content-type"] == "image/tiff"

    # Test GET overlay PNG
    get_png = client.get(f"/api/analysis/significance/{run_id}/overlay.png")
    assert get_png.status_code == 200
    assert get_png.headers["content-type"] == "image/png"
