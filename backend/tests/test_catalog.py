"""
Phase 1 → Phase 3a: Catalog seed and endpoint tests.

Updated for Phase 3a: `latest_observation_date` is now populated from the
database (or null when DB is unavailable). The old `latest_observation_status`
field has been replaced by the separate `last_catalogue_check` timestamp per
SPEC 15.3.

These tests use the YAML fallback path (no live DB required), so
`latest_observation_date` and `last_catalogue_check` will both be null.
"""
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api.catalog import load_catalog_seed, SEED_DIR

client = TestClient(app)


def test_seed_files_exist_and_loadable():
    variables = load_catalog_seed()
    assert len(variables) >= 1
    precip = next((v for v in variables if v.id == "precipitation"), None)
    assert precip is not None
    assert precip.name == "Precipitation"
    assert precip.category == "Atmosphere"
    assert len(precip.datasets) == 1

    ds = precip.datasets[0]
    assert ds.id == "gpcp_monthly_v23"
    assert ds.version == "V2.3"
    assert ds.units == "mm/day"
    assert ds.native_variable_name == "precip"
    assert ds.spatial_resolution == "2.5° × 2.5°"
    assert ds.temporal_resolution == "monthly"
    assert ds.start_date == "1979-01-01"

    # Phase 3a: latest_observation_date is populated from DB at runtime.
    # When reading from YAML fallback (no DB), it stays null — that is correct
    # and truthful (the YAML has no observation date either).
    # We do NOT assert it is null here: in production it may be populated.
    # We just assert the type is correct.
    assert ds.latest_observation_date is None or isinstance(ds.latest_observation_date, str)

    # Phase 3a: last_catalogue_check is a separate timestamp (SPEC 15.3)
    assert ds.last_catalogue_check is None or isinstance(ds.last_catalogue_check, str)

    # Unverified fields must be null with status "Needs validation"
    assert ds.doi is None
    assert ds.doi_status == "Needs validation"
    assert ds.update_latency is None
    assert ds.update_latency_status == "Needs validation"


def test_get_catalog_variables_endpoint():
    response = client.get("/api/catalog/variables")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    precip = data[0]
    assert precip["id"] == "precipitation"
    assert precip["name"] == "Precipitation"
    assert precip["default_dataset_id"] == "gpcp_monthly_v23"
    assert len(precip["datasets"]) == 1

    ds = precip["datasets"][0]
    assert ds["id"] == "gpcp_monthly_v23"

    # Phase 3a: response includes latest_observation_date and last_catalogue_check
    assert "latest_observation_date" in ds
    assert "last_catalogue_check" in ds

    # Either a valid YYYY-MM-DD string (from DB) or null (DB unavailable / not refreshed)
    if ds["latest_observation_date"] is not None:
        # Must be a valid ISO date string
        assert len(ds["latest_observation_date"]) == 10, (
            "latest_observation_date must be YYYY-MM-DD format"
        )
        assert ds["latest_observation_date"][4] == "-"


def test_get_catalog_datasets_endpoint():
    # Filter by variable=precipitation
    response = client.get("/api/catalog/datasets?variable=precipitation")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "gpcp_monthly_v23"
    assert data[0]["variable_id"] == "precipitation"
    assert data[0]["version"] == "V2.3"
    assert data[0]["units"] == "mm/day"

    # Phase 3a: both observation fields present
    assert "latest_observation_date" in data[0]
    assert "last_catalogue_check" in data[0]

    # Non-existent variable returns empty list
    resp_empty = client.get("/api/catalog/datasets?variable=nonexistent_var")
    assert resp_empty.status_code == 200
    assert resp_empty.json() == []

    # Without filter returns all datasets
    resp_all = client.get("/api/catalog/datasets")
    assert resp_all.status_code == 200
    assert len(resp_all.json()) >= 1
