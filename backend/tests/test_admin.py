"""
Tests for Admin API endpoints (Phase 3a).

POST /api/admin/catalog/refresh
- Token protection (401 without Bearer token or invalid token)
- Constant-time verification
- Successful refresh returns JSON summary
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings

client = TestClient(app)


def test_catalog_refresh_unauthorized_without_token():
    resp = client.post("/api/admin/catalog/refresh")
    assert resp.status_code == 401
    assert "Invalid or missing admin token" in resp.json()["detail"]


def test_catalog_refresh_unauthorized_with_wrong_token():
    resp = client.post(
        "/api/admin/catalog/refresh",
        headers={"Authorization": "Bearer wrong-token-12345"},
    )
    assert resp.status_code == 401
    assert "Invalid or missing admin token" in resp.json()["detail"]


@patch("backend.app.api.admin.refresh_all_datasets", new_callable=AsyncMock)
def test_catalog_refresh_authorized_all(mock_refresh):
    mock_refresh.return_value = {
        "gpcp_monthly_v23": {
            "status": "refreshed",
            "dataset_id": "gpcp_monthly_v23",
            "latest_observation_date": "2026-10-01",
            "last_catalogue_check": "2026-11-13T06:00:00+00:00",
            "changed": False,
        }
    }

    resp = client.post(
        "/api/admin/catalog/refresh",
        headers={"Authorization": f"Bearer {settings.ADMIN_TOKEN}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "refreshed" in data
    assert "gpcp_monthly_v23" in data["refreshed"]
    assert data["refreshed"]["gpcp_monthly_v23"]["latest_observation_date"] == "2026-10-01"


@patch("backend.app.api.admin.refresh_one_dataset", new_callable=AsyncMock)
def test_catalog_refresh_authorized_single(mock_refresh_one):
    mock_refresh_one.return_value = {
        "status": "refreshed",
        "dataset_id": "gpcp_monthly_v23",
        "latest_observation_date": "2026-10-01",
        "last_catalogue_check": "2026-11-13T06:00:00+00:00",
        "changed": False,
    }

    resp = client.post(
        "/api/admin/catalog/refresh?dataset_id=gpcp_monthly_v23",
        headers={"Authorization": f"Bearer {settings.ADMIN_TOKEN}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "refreshed" in data
    assert "gpcp_monthly_v23" in data["refreshed"]
    mock_refresh_one.assert_called_once()
