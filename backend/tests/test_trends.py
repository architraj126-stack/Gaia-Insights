"""
Tests for Trend Analysis Service (SPEC Section 8, 14.6).

Verifies:
1. Synthetic series with a known slope is recovered within tolerance.
2. White noise is not significant (no clear trend).
3. Seasonal series with a trend is detected by Seasonal Mann-Kendall.
4. AR(1) autocorrelated series where the modified test is more conservative than plain MK.
5. Too-short series gives 'insufficient data' per config minimum data rule.
6. Enriched series points and summary statistics all derive from a single unified series object.
"""
import numpy as np
import pytest

from backend.app.config import settings
from backend.app.services.trends import (
    analyze_timeseries_trends,
    compute_mann_kendall_tests,
    compute_ols_regression,
    compute_sens_slope,
    parse_date_to_decimal_year,
)


def test_known_slope_recovery():
    """Synthetic series with known slope (e.g. 2.5 mm/year) is recovered within tolerance."""
    np.random.seed(42)
    num_years = 20
    true_slope = 2.5
    true_intercept = 50.0

    points = []
    for y in range(2000, 2000 + num_years):
        for m in range(1, 13):
            dec_yr = y + (m - 0.5) / 12.0
            noise = np.random.normal(0, 0.2)
            val = true_intercept + true_slope * (dec_yr - 2000.0) + noise
            date_str = f"{y}-{m:02d}-01"
            points.append({
                "date": date_str,
                "value": round(float(val), 4),
                "units": "mm",
                "valid_cell_count": 10,
                "valid_area_km2": 1000.0,
                "is_missing": False,
                "flags": [],
            })

    enriched_pts, summary = analyze_timeseries_trends(
        points, aggregation="monthly", variable="precipitation"
    )

    ols_slope = summary["ols"]["slope_per_year"]
    sens_slope = summary["sens_slope"]["slope_per_year"]

    assert ols_slope is not None
    assert sens_slope is not None
    # Slope should be recovered within 0.1 mm/year tolerance
    assert abs(ols_slope - true_slope) < 0.1
    assert abs(sens_slope - true_slope) < 0.1
    assert summary["trend_direction"] == "increasing"
    assert summary["ols"]["p_value"] < 0.001
    assert summary["sens_slope"]["trend_direction"] == "increasing"
    assert summary["valid_n"] == 240


def test_white_noise_not_significant():
    """Pure white noise does not claim a significant trend."""
    np.random.seed(99)
    points = []
    for y in range(2000, 2015):
        for m in range(1, 13):
            val = 100.0 + np.random.normal(0, 5.0)
            date_str = f"{y}-{m:02d}-01"
            points.append({
                "date": date_str,
                "value": round(float(val), 4),
                "units": "mm",
                "valid_cell_count": 10,
                "valid_area_km2": 1000.0,
                "is_missing": False,
                "flags": [],
            })

    enriched_pts, summary = analyze_timeseries_trends(
        points, aggregation="monthly", variable="precipitation"
    )

    assert summary["trend_direction"] == "no clear trend"
    assert summary["ols"]["p_value"] > settings.TREND_ALPHA
    assert summary["mann_kendall"]["significant"] is False


def test_seasonal_series_with_trend():
    """Seasonal series (sinusoidal monthly cycle + trend) correctly detected by Seasonal Mann-Kendall."""
    np.random.seed(123)
    points = []
    trend_rate = 0.8
    for y in range(2000, 2020):
        for m in range(1, 13):
            # Monthly cycle: high in summer, low in winter
            seasonal_cycle = 15.0 * np.sin(2 * np.pi * (m - 1) / 12.0)
            dec_yr = y + (m - 0.5) / 12.0
            val = 50.0 + seasonal_cycle + trend_rate * (dec_yr - 2000.0) + np.random.normal(0, 1.0)
            date_str = f"{y}-{m:02d}-01"
            points.append({
                "date": date_str,
                "value": round(float(val), 4),
                "units": "mm",
                "valid_cell_count": 10,
                "valid_area_km2": 1000.0,
                "is_missing": False,
                "flags": [],
            })

    enriched_pts, summary = analyze_timeseries_trends(
        points, aggregation="monthly", variable="precipitation"
    )

    smk = summary["seasonal_mann_kendall"]
    assert smk is not None
    assert smk["trend"] == "increasing"
    assert smk["significant"] is True
    assert smk["p_value"] < 0.05
    assert smk["period"] == 12


def test_ar1_modified_mk_more_conservative():
    """
    On an AR(1) autocorrelated series, Hamed-Rao modified Mann-Kendall
    adjusts variance upward, making the test more conservative (lower |z| and higher p-value).
    """
    np.random.seed(42)
    n = 100
    phi = 0.75  # Strong positive autocorrelation
    eps = np.random.normal(0, 1, n)
    ar1 = np.zeros(n)
    ar1[0] = eps[0]
    for i in range(1, n):
        ar1[i] = phi * ar1[i - 1] + eps[i]

    # Add a small trend
    y = 0.04 * np.arange(n) + ar1

    mk_dict, _, mod_dict = compute_mann_kendall_tests(
        y_valid=y,
        y_all_with_nans=list(y),
        aggregation="monthly",
        alpha=0.05,
    )

    # Modified test should adjust for autocorrelation:
    # variance of S is larger, test statistic z is smaller, and p-value is larger.
    assert abs(mod_dict["z"]) < abs(mk_dict["z"])
    assert mod_dict["p_value"] > mk_dict["p_value"]
    assert mod_dict["method"] == "hamed_rao"


def test_too_short_series_insufficient_data():
    """Series with fewer than min_data_points yields 'insufficient data' without crashes."""
    short_points = [
        {"date": "2020-01-01", "value": 12.0, "is_missing": False, "units": "mm"},
        {"date": "2020-02-01", "value": 15.0, "is_missing": False, "units": "mm"},
        {"date": "2020-03-01", "value": 11.0, "is_missing": False, "units": "mm"},
        {"date": "2020-04-01", "value": 14.0, "is_missing": False, "units": "mm"},
        {"date": "2020-05-01", "value": 13.0, "is_missing": False, "units": "mm"},
    ]

    enriched_pts, summary = analyze_timeseries_trends(
        short_points, aggregation="monthly", min_data_points=12
    )

    assert summary["trend_direction"] == "insufficient data"
    assert summary["rate_of_change"] is None
    assert summary["ols"]["trend_direction"] == "insufficient data"
    assert summary["sens_slope"]["trend_direction"] == "insufficient data"
    assert summary["valid_n"] == 5
    assert summary["completeness"]["valid"] == 5
    assert summary["completeness"]["pct"] < 100.0 or summary["completeness"]["expected"] == 5


def test_unified_series_derivation():
    """
    Asserts that chart points, regression lines, confidence bands,
    moving averages, and summary metrics all derive from the exact same series object.
    """
    points = [
        {"date": f"2010-{m:02d}-01", "value": 10.0 + m * 0.5, "units": "mm", "is_missing": False}
        for m in range(1, 13)
    ]
    # Inject a real missing month to verify gap preservation
    points[4]["value"] = None
    points[4]["is_missing"] = True

    enriched_pts, summary = analyze_timeseries_trends(
        points, aggregation="monthly", min_data_points=10
    )

    # 1. Total length of points matches input exactly
    assert len(enriched_pts) == len(points)

    # 2. Missing point preserved with null value
    assert enriched_pts[4]["value"] is None
    assert enriched_pts[4]["is_missing"] is True

    # 3. Chart lines (fitted_ols, ols_ci, sens_line, moving_avg) are populated on each point
    for idx, pt in enumerate(enriched_pts):
        assert "fitted_ols" in pt
        assert "ols_ci_lower" in pt
        assert "ols_ci_upper" in pt
        assert "sens_line" in pt
        assert "moving_avg" in pt

        if pt["fitted_ols"] is not None and pt["ols_ci_lower"] is not None and pt["ols_ci_upper"] is not None:
            # Regression line must strictly lie within its confidence band
            assert pt["ols_ci_lower"] <= pt["fitted_ols"] <= pt["ols_ci_upper"]

    # 4. Summary metrics valid_n matches count of non-missing values
    non_missing_count = sum(1 for p in enriched_pts if p["value"] is not None)
    assert summary["valid_n"] == non_missing_count == 11
    assert summary["completeness"]["valid"] == 11
    assert summary["completeness"]["expected"] == 12
    assert summary["completeness"]["pct"] == round(11 / 12 * 100.0, 2)


def test_api_timeseries_tied_to_exact_stored_series():
    """
    Integration test asserting that POST /api/analysis/timeseries summary and points
    are tied to the exact stored series returned by GET /api/results/series/{series_id}.
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    # Use a small bounding box for quick spatial extraction
    poly = {
        "type": "Polygon",
        "coordinates": [[
            [10.0, 45.0],
            [15.0, 45.0],
            [15.0, 50.0],
            [10.0, 50.0],
            [10.0, 45.0],
        ]]
    }

    req_payload = {
        "dataset_id": "gpcp_monthly_v23",
        "variable": "precipitation",
        "geometry": poly,
        "start_date": "2015-01-01",
        "end_date": "2018-12-01",
        "aggregation": "monthly",
    }

    res = client.post("/api/analysis/timeseries", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert "series_url" in data
    assert "summary" in data
    assert "points" in data
    summary = data["summary"]
    points = data["points"]

    assert summary["valid_n"] == len([p for p in points if p["value"] is not None])
    assert summary["completeness"]["valid"] == summary["valid_n"]
    assert "ols" in summary
    assert "sens_slope" in summary
    assert "mann_kendall" in summary
    assert "modified_mann_kendall" in summary

    # Retrieve from the series_url
    series_res = client.get(data["series_url"])
    assert series_res.status_code == 200
    stored_series = series_res.json()

    # The stored points and summary must be identical
    assert stored_series["summary"] == summary
    assert len(stored_series["points"]) == len(points)
    for p_resp, p_store in zip(points, stored_series["points"]):
        assert p_resp["date"] == p_store["date"]
        assert p_resp["value"] == p_store["value"]
        assert p_resp.get("fitted_ols") == p_store.get("fitted_ols")
        assert p_resp.get("ols_ci_lower") == p_store.get("ols_ci_lower")
        assert p_resp.get("ols_ci_upper") == p_store.get("ols_ci_upper")
        assert p_resp.get("sens_line") == p_store.get("sens_line")
        assert p_resp.get("moving_avg") == p_store.get("moving_avg")
