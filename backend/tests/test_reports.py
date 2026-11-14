"""
Automated Tests for Report Generation Service and Exports (SPEC 10.7, 10.8, 15.4, 17.3).

Tests:
1. Golden test: report numbers equal the exact API numbers for the same run (zero recomputed/typed).
2. Section toggles work (enable/disable individual sections).
3. PDF text contains version, DOI, and the limitations section.
4. Refusal to combine runs with conflicting dataset versions, regions, or dates.
5. FastAPI report endpoints (POST /api/reports, GET /api/reports/{id}, GET /api/reports/{id}/pdf, GET /api/reports/{id}/csv).
"""
import json
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.app.main import app
from backend.app.services.reports import (
    create_report,
    load_run_data,
    validate_runs_consistency,
    RESULTS_CACHE_DIR,
    OUTPUTS_DIR,
)


@pytest.fixture
def mock_run_environment(tmp_path: Path):
    """
    Creates temporary cached analysis runs for Page 3, Page 4, and Page 5 with exact known numbers.
    """
    p3_id = "test_p3_series"
    p4_id = "test_p4_change"
    p5_id = "test_p5_significance"

    # 1. Page 3 Run Payload (Trends)
    p3_data = {
        "series_id": p3_id,
        "run_id": "run_p3_123",
        "dataset": {
            "id": "gpcp_monthly_v23",
            "version": "v2.3",
            "variable": "precipitation",
            "units": "mm/month",
        },
        "coverage": {
            "actual_start": "1990-01-01",
            "actual_end": "2025-12-01",
            "valid_steps": 432,
            "expected_steps": 432,
            "completeness_pct": 100.0,
        },
        "points": [
            {
                "date": f"{y}-{m:02d}-01",
                "value": 65.4 + (y - 1990) * 0.25,
                "units": "mm/month",
                "is_missing": False,
                "flags": ["valid"],
                "valid_cells": 18,
                "valid_area_km2": 150000.0,
                "sens_line": 65.4 + (y - 1990) * 0.25,
                "fitted_ols": 65.3 + (y - 1990) * 0.25,
                "ols_ci_lower": 62.0,
                "ols_ci_upper": 69.0,
            }
            for y in range(1990, 2026)
            for m in range(1, 13)
        ],
        "summary": {
            "mean": 69.775,
            "slope": 0.250,
            "sens_slope": 0.250,
            "ols_ci_lower": 0.180,
            "ols_ci_upper": 0.320,
            "trend_direction": "increasing",
            "total_change": 8.75,
            "units": "mm/month",
            "valid_steps": 432,
        },
        "provenance": {
            "dataset_id": "gpcp_monthly_v23",
            "dataset_version": "v2.3",
            "variable": "precipitation",
            "geometry_hash": "geom_hash_europe",
            "region_id": "Western Europe",
            "actual_start": "1990-01-01",
            "actual_end": "2025-12-01",
            "output_units": "mm/month",
        },
        "bounds": [[40.0, -10.0], [55.0, 15.0]],
    }

    # 2. Page 4 Run Payload (Change Detection)
    p4_data = {
        "job_id": "job_c456",
        "run_id": p4_id,
        "status": "completed",
        "units": "mm/year",
        "metric": "absolute",
        "bounds": [[40.0, -10.0], [55.0, 15.0]],
        "spatial_summary": {
            "area_weighted_mean_change": 34.62,
            "share_increasing_pct": 68.4,
            "share_decreasing_pct": 26.1,
            "share_no_change_pct": 5.5,
            "highest_change": {"value": 142.8, "lat": 48.0, "lon": 5.0},
            "lowest_change": {"value": -84.2, "lat": 42.0, "lon": -2.0},
            "valid_area_km2": 1800000.0,
            "total_region_area_km2": 2000000.0,
            "nodata_area_km2": 200000.0,
            "nodata_share_pct": 10.0,
            "valid_cell_count": 28,
            "intersecting_cell_count": 32,
        },
        "provenance": {
            "dataset_id": "gpcp_monthly_v23",
            "dataset_version": "v2.3",
            "geometry_hash": "geom_hash_europe",
            "baseline_period": [1990, 2005],
            "comparison_period": [2006, 2025],
        },
    }

    # 3. Page 5 Run Payload (Significance)
    p5_data = {
        "run_id": p5_id,
        "status": "completed",
        "bounds": [[40.0, -10.0], [55.0, 15.0]],
        "regional": {
            "test_name": "Seasonal Mann-Kendall with Hamed-Rao Variance Correction",
            "null_hypothesis": "There is no monotonic trend over time in the regional series.",
            "test_statistic": 3.125,
            "raw_p_value": 0.0018,
            "sens_slope": 0.250,
            "ci_lower": 0.175,
            "ci_upper": 0.325,
            "sample_size": 432,
            "alpha": 0.05,
            "ci_level": 0.95,
            "lag1_autocorrelation": 0.214,
            "autocorrelation_handling": "hamed_rao",
            "choice_documentation": "Positive lag-1 autocorrelation detected (r1 = 0.2140 > 0.10). Hamed-Rao variance inflation applied.",
            "interpretation": "The regional series exhibits a statistically significant monotonic trend (p = 0.0018 < 0.05). Note that statistical significance does not imply large environmental magnitude or a causal mechanism.",
            "is_significant": True,
        },
        "spatial": {
            "overlay_url": f"/api/analysis/significance/{p5_id}/overlay.png",
            "geotiff_url": f"/api/analysis/significance/{p5_id}/geotiff",
            "bounds": [[40.0, -10.0], [55.0, 15.0]],
            "legend": {
                "title": "Statistical Significance Classes (SPEC 10.4)",
                "p_value_mode": "Benjamini-Hochberg FDR Adjusted",
                "alpha": 0.05,
                "classes": [],
            },
            "class_counts": {
                "significant_increase": 14,
                "significant_decrease": 3,
                "not_significant": 11,
                "insufficient_data": 0,
                "not_covered": 4,
            },
            "min_valid_years": 10,
            "fdr_correction": True,
            "alpha": 0.05,
        },
        "provenance": {
            "dataset_id": "gpcp_monthly_v23",
            "dataset_version": "v2.3",
            "geometry_hash": "geom_hash_europe",
            "alpha": 0.05,
            "fdr_correction": True,
        },
    }

    # Save files to cache / outputs
    RESULTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(RESULTS_CACHE_DIR / f"{p3_id}.json", "w", encoding="utf-8") as f:
        json.dump(p3_data, f)
    with open(OUTPUTS_DIR / f"result_{p4_id}.json", "w", encoding="utf-8") as f:
        json.dump(p4_data, f)
    with open(OUTPUTS_DIR / f"significance_result_{p5_id}.json", "w", encoding="utf-8") as f:
        json.dump(p5_data, f)

    return {
        "series_id": p3_id,
        "change_run_id": p4_id,
        "significance_run_id": p5_id,
        "p3_data": p3_data,
        "p4_data": p4_data,
        "p5_data": p5_data,
    }


def test_golden_report_numbers_equal_api_numbers_for_same_run(mock_run_environment):
    """
    GOLDEN TEST: Asserts every single number in the report equals the stored API numbers
    for the exact same runs (Rule 1, SPEC 10.7).
    """
    env = mock_run_environment
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        report = create_report(
            series_id=env["series_id"],
            change_run_id=env["change_run_id"],
            significance_run_id=env["significance_run_id"],
            output_dir=tmp_path,
        )

        p3 = env["p3_data"]
        p4 = env["p4_data"]
        p5 = env["p5_data"]

        # 1. Historical Trends numbers match exactly
        assert report["trends_summary"]["mean"] == p3["summary"]["mean"]
        assert report["trends_summary"]["slope"] == p3["summary"]["slope"]
        assert report["trends_summary"]["sens_slope"] == p3["summary"]["sens_slope"]
        assert report["trends_summary"]["ols_ci_lower"] == p3["summary"]["ols_ci_lower"]
        assert report["trends_summary"]["ols_ci_upper"] == p3["summary"]["ols_ci_upper"]

        # 2. Change Detection numbers match exactly
        assert report["change_summary"]["area_weighted_mean_change"] == p4["spatial_summary"]["area_weighted_mean_change"]
        assert report["change_summary"]["share_increasing_pct"] == p4["spatial_summary"]["share_increasing_pct"]
        assert report["change_summary"]["share_decreasing_pct"] == p4["spatial_summary"]["share_decreasing_pct"]
        assert report["change_summary"]["highest_change"]["value"] == p4["spatial_summary"]["highest_change"]["value"]
        assert report["change_summary"]["lowest_change"]["value"] == p4["spatial_summary"]["lowest_change"]["value"]

        # 3. Significance numbers match exactly
        assert report["significance_info"]["regional"]["raw_p_value"] == p5["regional"]["raw_p_value"]
        assert report["significance_info"]["regional"]["sens_slope"] == p5["regional"]["sens_slope"]
        assert report["significance_info"]["regional"]["test_statistic"] == p5["regional"]["test_statistic"]
        assert report["significance_info"]["regional"]["sample_size"] == p5["regional"]["sample_size"]
        assert report["significance_info"]["spatial"]["class_counts"]["significant_increase"] == p5["spatial"]["class_counts"]["significant_increase"]
        assert report["significance_info"]["spatial"]["class_counts"]["significant_decrease"] == p5["spatial"]["class_counts"]["significant_decrease"]

        # 4. Executive summary metrics match exactly
        exec_metrics = report["executive_summary"]["key_metrics"]
        assert "69.78" in exec_metrics["regional_mean"]
        assert "+0.250" in exec_metrics["sen_slope"]
        assert "+34.62" in exec_metrics["area_weighted_mean_change"]
        assert "68.4%" in exec_metrics["increasing_area_share"]
        assert "0.0018" in exec_metrics["significance_p_value"]


def test_section_toggles_enable_disable_content(mock_run_environment):
    """
    Tests that section toggles selectively enable/disable report components.
    """
    env = mock_run_environment
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Disable trends and change sections
        custom_sections = {
            "executive_summary": True,
            "dataset_and_study_area": True,
            "historical_trends": False,
            "change_detection": False,
            "statistical_significance": True,
            "data_quality": True,
            "methodology_and_references": True,
        }

        report = create_report(
            series_id=env["series_id"],
            change_run_id=env["change_run_id"],
            significance_run_id=env["significance_run_id"],
            sections=custom_sections,
            output_dir=tmp_path,
        )

        assert report["sections_enabled"]["historical_trends"] is False
        assert report["sections_enabled"]["change_detection"] is False
        assert report["sections_enabled"]["statistical_significance"] is True

        pdf_path = tmp_path / f"report_{report['report_id']}.pdf"
        assert pdf_path.exists()

        reader = PdfReader(str(pdf_path))
        pdf_text = " ".join([page.extract_text() for page in reader.pages])

        # Enabled sections present
        assert "1. Executive Summary" in pdf_text
        assert "2. Dataset and Study Area" in pdf_text
        assert "5. Statistical Significance" in pdf_text

        # Disabled sections NOT present as main headings
        assert "3. Historical Trend Analysis" not in pdf_text
        assert "4. Spatial Change Detection" not in pdf_text


def test_pdf_text_contains_version_doi_and_limitations(mock_run_environment):
    """
    Validates that compiled PDF contains exact product version, DOI,
    access date, and limitations section (SPEC 10.7, 10.8, 15.4).
    """
    env = mock_run_environment
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        report = create_report(
            series_id=env["series_id"],
            change_run_id=env["change_run_id"],
            significance_run_id=env["significance_run_id"],
            output_dir=tmp_path,
        )

        pdf_path = tmp_path / f"report_{report['report_id']}.pdf"
        assert pdf_path.exists()

        reader = PdfReader(str(pdf_path))
        pdf_text = " ".join([page.extract_text() for page in reader.pages])

        # Version & DOI
        assert "v2.3" in pdf_text
        assert "10.7289/V56971M6" in pdf_text

        # Scientific Cautions & Limitations
        assert "A p-value is not the probability that the null hypothesis is true" in pdf_text
        assert "Statistical significance does not imply large environmental magnitude" in pdf_text
        assert "An observed statistical trend does not establish a causal explanation" in pdf_text
        assert "6. Data Quality, Completeness & Method Limitations" in pdf_text
        assert "7. Methodology & Bibliographic References" in pdf_text


def test_service_refuses_to_combine_inconsistent_runs(mock_run_environment):
    """
    Validates that validate_runs_consistency raises ValueError when attempting
    to combine runs with conflicting versions, regions, or date ranges.
    """
    env = mock_run_environment
    p3 = env["p3_data"]
    p4 = env["p4_data"]
    p5 = env["p5_data"]

    # 1. Dataset Version Mismatch
    bad_p4_version = json.loads(json.dumps(p4))
    bad_p4_version["provenance"]["dataset_version"] = "v3.0"
    with pytest.raises(ValueError, match="Dataset version mismatch"):
        validate_runs_consistency(p3, bad_p4_version, p5)

    # 2. Region Mismatch (differing geometry hash)
    bad_p5_region = json.loads(json.dumps(p5))
    bad_p5_region["provenance"]["geometry_hash"] = "geom_hash_africa"
    with pytest.raises(ValueError, match="Study area mismatch"):
        validate_runs_consistency(p3, p4, bad_p5_region)

    # 3. Date Range Mismatch (Page 4 comparison year extends past Page 3 coverage)
    bad_p4_dates = json.loads(json.dumps(p4))
    bad_p4_dates["provenance"]["comparison_period"] = [2006, 2035]
    with pytest.raises(ValueError, match="Date range mismatch"):
        validate_runs_consistency(p3, bad_p4_dates, p5)


def test_api_report_endpoints(mock_run_environment):
    """
    Validates FastAPI endpoints:
    - POST /api/reports
    - GET /api/reports/{id}
    - GET /api/reports/{id}/pdf
    - GET /api/reports/{id}/csv
    """
    env = mock_run_environment
    client = TestClient(app)

    # 1. Create Report
    post_payload = {
        "title": "Automated Golden Verification Report",
        "series_id": env["series_id"],
        "change_run_id": env["change_run_id"],
        "significance_run_id": env["significance_run_id"],
        "sections": {
            "executive_summary": True,
            "dataset_and_study_area": True,
            "historical_trends": True,
            "change_detection": True,
            "statistical_significance": True,
            "data_quality": True,
            "methodology_and_references": True,
        },
    }

    resp = client.post("/api/reports", json=post_payload)
    assert resp.status_code == 201
    report_json = resp.json()
    report_id = report_json["report_id"]
    assert report_id.startswith("rep_")
    assert report_json["status"] == "completed"
    assert "pdf_url" in report_json["downloads"]
    assert "csv_url" in report_json["downloads"]

    # 2. Get Report Metadata
    resp_get = client.get(f"/api/reports/{report_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["report_id"] == report_id

    # 3. Download PDF
    resp_pdf = client.get(f"/api/reports/{report_id}/pdf")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"
    assert len(resp_pdf.content) > 1000

    # 4. Download CSV
    resp_csv = client.get(f"/api/reports/{report_id}/csv")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert b"date,value,units" in resp_csv.content
