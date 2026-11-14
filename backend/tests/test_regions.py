import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_search_regions():
    # Search for a country
    resp = client.get("/api/regions/search?q=Fiji")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    fiji = next((r for r in data if r["name"] == "Fiji"), None)
    assert fiji is not None
    assert fiji["type"] == "admin-0"
    assert "admin0_" in fiji["id"]

    # Search for Chukotka (Admin-1)
    resp2 = client.get("/api/regions/search?q=Chukotka")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2) >= 1
    assert any("chukotka" in r["name"].lower() for r in data2)


def test_get_region_geometry():
    # Search for Fiji to obtain its ID
    resp = client.get("/api/regions/search?q=Fiji")
    fiji = resp.json()[0]
    region_id = fiji["id"]

    # Fetch geometry
    geom_resp = client.get(f"/api/regions/{region_id}/geometry")
    assert geom_resp.status_code == 200
    geom_data = geom_resp.json()
    assert geom_data["id"] == region_id
    assert geom_data["name"] == "Fiji"
    assert "geometry" in geom_data
    assert geom_data["geometry"]["type"] in ["Polygon", "MultiPolygon"]
    assert "bbox" in geom_data


def test_validate_country():
    """Case 1: A country (Fiji or France)"""
    resp = client.get("/api/regions/search?q=France")
    france = resp.json()[0]
    geom_resp = client.get(f"/api/regions/{france['id']}/geometry")
    france_geom = geom_resp.json()["geometry"]

    val_resp = client.post("/api/regions/validate", json={"geometry": france_geom, "crs": "EPSG:4326"})
    assert val_resp.status_code == 200
    res = val_resp.json()
    assert res["status"] == "valid"
    assert res["area_km2"] > 500000.0  # France is ~643,000 km2
    assert len(res["bbox"]) == 4
    assert len(res["centroid"]) == 2


def test_validate_hand_drawn_polygon():
    """Case 2: A hand-drawn arbitrary polygon"""
    poly = {
        "type": "Polygon",
        "coordinates": [
            [[10.0, 50.0], [15.0, 50.0], [15.0, 55.0], [10.0, 55.0], [10.0, 50.0]]
        ]
    }
    resp = client.post("/api/regions/validate", json={"geometry": poly, "crs": "EPSG:4326"})
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "valid"
    assert res["geometry"]["type"] == "Polygon"
    assert res["area_km2"] > 150000.0
    assert res["centroid"][0] == 12.5
    assert res["centroid"][1] == 52.5


def test_validate_rectangle():
    """Case 3: A rectangle (e.g. drawn by box tool)"""
    rect = {
        "type": "Polygon",
        "coordinates": [
            [[-100.0, 30.0], [-90.0, 30.0], [-90.0, 40.0], [-100.0, 40.0], [-100.0, 30.0]]
        ]
    }
    resp = client.post("/api/regions/validate", json={"geometry": rect, "crs": "EPSG:4326"})
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "valid"
    assert res["bbox"] == [-100.0, 30.0, -90.0, 40.0]
    assert res["centroid"] == [-95.0, 35.0]
    assert res["area_km2"] > 800000.0


def test_validate_antimeridian_crossing():
    """Case 4: Antimeridian crossings (Fiji, Chukotka, and drawn crossing polygon)"""
    # 4a: Fiji boundary
    fiji_search = client.get("/api/regions/search?q=Fiji").json()[0]
    fiji_geom = client.get(f"/api/regions/{fiji_search['id']}/geometry").json()["geometry"]
    resp_fiji = client.post("/api/regions/validate", json={"geometry": fiji_geom, "crs": "EPSG:4326"})
    assert resp_fiji.status_code == 200
    res_fiji = resp_fiji.json()
    assert res_fiji["status"] == "valid"
    assert res_fiji["bbox"][0] <= -178.0 or res_fiji["bbox"][2] >= 178.0

    # 4b: Chukotka boundary
    chu_search = [r for r in client.get("/api/regions/search?q=Chukotka").json() if "chukotka" in r["name"].lower()][0]
    chu_geom = client.get(f"/api/regions/{chu_search['id']}/geometry").json()["geometry"]
    resp_chu = client.post("/api/regions/validate", json={"geometry": chu_geom, "crs": "EPSG:4326"})
    assert resp_chu.status_code == 200
    res_chu = resp_chu.json()
    assert res_chu["status"] == "valid"

    # 4c: Hand-drawn polygon spanning across 180° meridian (175° to -175° / 185°)
    crossing_poly = {
        "type": "Polygon",
        "coordinates": [
            [[175.0, 10.0], [-175.0, 10.0], [-175.0, 20.0], [175.0, 20.0], [175.0, 10.0]]
        ]
    }
    resp_cross = client.post("/api/regions/validate", json={"geometry": crossing_poly, "crs": "EPSG:4326"})
    assert resp_cross.status_code == 200
    res_cross = resp_cross.json()
    assert res_cross["status"] == "valid"
    assert res_cross["geometry"]["type"] == "MultiPolygon"
    assert any("antimeridian" in w.lower() for w in res_cross["warnings"])
    # The area should represent a ~10-degree wide strip, not 350 degrees around the globe!
    assert res_cross["area_km2"] < 2500000.0


def test_validate_self_intersecting_bowtie():
    """Case 5: Self-intersecting bowtie polygon repaired by make_valid"""
    bowtie = {
        "type": "Polygon",
        "coordinates": [
            [[0.0, 0.0], [2.0, 2.0], [2.0, 0.0], [0.0, 2.0], [0.0, 0.0]]
        ]
    }
    resp = client.post("/api/regions/validate", json={"geometry": bowtie, "crs": "EPSG:4326"})
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "valid"
    assert any("make_valid" in w or "invalid" in w for w in res["warnings"])
    assert res["geometry"]["type"] in ["MultiPolygon", "Polygon", "GeometryCollection"]
    assert res["area_km2"] > 0.0


def test_validate_tiny_polygon():
    """Case 6: A tiny polygon (< 1 grid cell)"""
    tiny = {
        "type": "Polygon",
        "coordinates": [
            [[0.0, 0.0], [0.001, 0.0], [0.001, 0.001], [0.0, 0.001], [0.0, 0.0]]
        ]
    }
    resp = client.post("/api/regions/validate", json={"geometry": tiny, "crs": "EPSG:4326"})
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "valid"
    assert res["area_km2"] < 1.0  # Approx 0.012 km2


def test_validate_point_buffer():
    """Point + radius -> geodesic buffer polygon"""
    payload = {
        "point": [0.0, 0.0],
        "radius_km": 50.0,
        "crs": "EPSG:4326"
    }
    resp = client.post("/api/regions/validate", json=payload)
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "valid"
    assert res["geometry"]["type"] == "Polygon"
    # Expected area for 50km radius circle: ~pi * 50^2 = 7853.98 km2
    assert 7800.0 < res["area_km2"] < 7900.0
    assert any("buffer" in w.lower() for w in res["warnings"])
