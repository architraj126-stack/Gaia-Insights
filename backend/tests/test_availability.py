import json
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_availability_country_available():
    """Valid country query against GPCP monthly V2.3 returns Available"""
    # France bounding box approx
    resp = client.get("/api/datasets/gpcp_monthly_v23/availability?bbox=-5,42,8,51&start=1990-01-01&end=2020-12-31")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dataset_id"] == "gpcp_monthly_v23"
    assert data["status"] == "Available"
    assert data["cell_count"] > 0
    assert data["spatial_coverage_percent"] == 100.0
    assert data["valid_date_range"]["start"] == "1979-01-01"

    # Phase 3a: latest_observation_date is populated from DB at runtime.
    # When DB is unavailable (test environment), it may be None.
    # The old 'latest_observation_status' field has been replaced by
    # 'last_catalogue_check' (a separate UTC timestamp) per SPEC 15.3.
    assert "latest_observation_date" in data["valid_date_range"]
    assert "last_catalogue_check" in data["valid_date_range"]
    # The deprecated key must NOT be present
    assert "latest_observation_status" not in data["valid_date_range"]


def test_availability_tiny_polygon_warnings():
    """Tiny polygon triggers cell count warning and size warning"""
    tiny_geom = {
        "type": "Polygon",
        "coordinates": [[[0.0, 0.0], [0.005, 0.0], [0.005, 0.005], [0.0, 0.005], [0.0, 0.0]]]
    }
    resp = client.get(
        f"/api/datasets/gpcp_monthly_v23/availability?geometry={json.dumps(tiny_geom)}&start=1990-01-01"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["cell_count"] == 0
    warnings = data["warnings"]
    assert any("significantly smaller than one grid cell" in w for w in warnings)
    assert any("0 grid cell centres" in w for w in warnings)


def test_availability_temporal_partial():
    """Requesting dates prior to dataset start_date (1979) returns Partial with warning"""
    resp = client.get(
        "/api/datasets/gpcp_monthly_v23/availability?bbox=0,10,10,20&start=1960-01-01&end=2000-01-01"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "Partial"
    warnings = data["warnings"]
    assert any("precedes dataset start date" in w for w in warnings)


def test_availability_post_endpoint():
    """POST /api/datasets/{id}/availability works with JSON payload"""
    payload = {
        "bbox": [-10.0, 35.0, 5.0, 45.0],
        "start": "1995-01-01",
        "end": "2015-12-31"
    }
    resp = client.post("/api/datasets/gpcp_monthly_v23/availability", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "Available"
    assert data["cell_count"] > 0


def test_availability_not_found():
    resp = client.get("/api/datasets/non_existent_dataset/availability?bbox=0,0,1,1")
    assert resp.status_code == 404
