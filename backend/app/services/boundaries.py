import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.prepared import prep

logger = logging.getLogger(__name__)

BOUNDARIES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "boundaries"

_ADMIN_0_CACHE: Optional[List[Dict[str, Any]]] = None
_ADMIN_1_CACHE: Optional[List[Dict[str, Any]]] = None
_ID_LOOKUP: Optional[Dict[str, Dict[str, Any]]] = None
_LAND_UNION: Optional[BaseGeometry] = None
_PREP_LAND: Optional[Any] = None


def _load_boundaries_cache() -> None:
    global _ADMIN_0_CACHE, _ADMIN_1_CACHE, _ID_LOOKUP
    if _ADMIN_0_CACHE is not None and _ID_LOOKUP is not None:
        return

    _ADMIN_0_CACHE = []
    _ADMIN_1_CACHE = []
    _ID_LOOKUP = {}

    admin_0_path = BOUNDARIES_DIR / "admin_0.geojson"
    if admin_0_path.exists():
        try:
            with open(admin_0_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for feat in data.get("features", []):
                    feat_id = feat.get("id") or feat.get("properties", {}).get("id")
                    if feat_id:
                        _ADMIN_0_CACHE.append(feat)
                        _ID_LOOKUP[feat_id] = feat
            logger.info("Loaded %d Admin-0 boundaries into cache", len(_ADMIN_0_CACHE))
        except Exception as e:
            logger.error("Failed to load admin_0.geojson: %s", e)

    admin_1_path = BOUNDARIES_DIR / "admin_1.geojson"
    if admin_1_path.exists():
        try:
            with open(admin_1_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for feat in data.get("features", []):
                    feat_id = feat.get("id") or feat.get("properties", {}).get("id")
                    if feat_id:
                        _ADMIN_1_CACHE.append(feat)
                        _ID_LOOKUP[feat_id] = feat
            logger.info("Loaded %d Admin-1 boundaries into cache", len(_ADMIN_1_CACHE))
        except Exception as e:
            logger.error("Failed to load admin_1.geojson: %s", e)


def search_boundaries(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """
    Searches administrative boundaries (Admin-0 countries and Admin-1 states/provinces)
    for matching names, ISO codes, or parent countries.
    """
    _load_boundaries_cache()
    assert _ADMIN_0_CACHE is not None
    assert _ADMIN_1_CACHE is not None

    q = query.strip().lower()
    if not q:
        # Return prominent countries as default list
        default_results = []
        for feat in _ADMIN_0_CACHE[:limit]:
            props = feat.get("properties", {})
            default_results.append({
                "id": feat.get("id") or props.get("id"),
                "name": props.get("name"),
                "type": props.get("type", "admin-0"),
                "subtype": props.get("subtype", "country"),
                "country": props.get("admin") or props.get("name"),
                "iso_a3": props.get("iso_a3"),
                "bbox": props.get("bbox")
            })
        return default_results

    exact_matches: List[Dict[str, Any]] = []
    prefix_matches: List[Dict[str, Any]] = []
    contains_matches: List[Dict[str, Any]] = []

    # Prioritize Admin-0 first, then Admin-1
    for feat in _ADMIN_0_CACHE + _ADMIN_1_CACHE:
        props = feat.get("properties", {})
        name = (props.get("name") or "").lower()
        local_name = (props.get("local_name") or "").lower()
        country = (props.get("country") or props.get("admin") or "").lower()
        iso_a3 = (props.get("iso_a3") or props.get("adm0_a3") or "").lower()

        item = {
            "id": feat.get("id") or props.get("id"),
            "name": props.get("name"),
            "local_name": props.get("local_name"),
            "type": props.get("type", "admin-0"),
            "subtype": props.get("subtype"),
            "country": props.get("country") or props.get("admin"),
            "iso_a3": props.get("iso_a3") or props.get("adm0_a3"),
            "bbox": props.get("bbox")
        }

        if name == q or local_name == q or iso_a3 == q:
            exact_matches.append(item)
        elif name.startswith(q) or local_name.startswith(q) or iso_a3.startswith(q):
            prefix_matches.append(item)
        elif q in name or q in local_name or q in country:
            contains_matches.append(item)

        if len(exact_matches) + len(prefix_matches) + len(contains_matches) >= limit * 3:
            break

    combined = exact_matches + prefix_matches + contains_matches
    return combined[:limit]


def get_boundary_by_id(region_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves the boundary GeoJSON feature by its unique region ID.
    """
    _load_boundaries_cache()
    assert _ID_LOOKUP is not None

    feat = _ID_LOOKUP.get(region_id)
    if not feat:
        return None

    props = feat.get("properties", {})
    return {
        "id": feat.get("id") or props.get("id"),
        "name": props.get("name"),
        "local_name": props.get("local_name"),
        "type": props.get("type", "admin-0"),
        "subtype": props.get("subtype"),
        "country": props.get("country") or props.get("admin"),
        "iso_a3": props.get("iso_a3") or props.get("adm0_a3"),
        "crs": "EPSG:4326",
        "bbox": props.get("bbox"),
        "geometry": feat.get("geometry")
    }


def get_land_union() -> BaseGeometry:
    """
    Returns the unified MultiPolygon representing all terrestrial land boundaries (from Natural Earth Admin-0).
    Cached in memory for high-performance spatial containment and coverage checks.
    """
    global _LAND_UNION, _PREP_LAND
    if _LAND_UNION is None:
        _load_boundaries_cache()
        assert _ADMIN_0_CACHE is not None
        geoms = [shape(feat["geometry"]) for feat in _ADMIN_0_CACHE if feat.get("geometry")]
        _LAND_UNION = unary_union(geoms)
        _PREP_LAND = prep(_LAND_UNION)
    return _LAND_UNION


def is_point_on_land(lon: float, lat: float) -> bool:
    """Tests if a coordinate (lon, lat) falls on land."""
    get_land_union()
    assert _PREP_LAND is not None
    p = Point(lon, lat)
    return bool(_PREP_LAND.intersects(p))


def calculate_geometry_land_ratio(geom: Any) -> float:
    """
    Calculates the spatial ratio (0.0 to 1.0) of the given geometry that intersects terrestrial land.
    Used for enforcing land-only and ocean-only variable coverage rules (SPEC 6.3, SPEC 14.1).
    """
    if isinstance(geom, dict):
        geom = shape(geom)
    land = get_land_union()
    if not geom.intersects(land):
        return 0.0
    if land.contains(geom):
        return 1.0

    try:
        inter = geom.intersection(land)
        if geom.area <= 0.0:
            return 1.0 if land.contains(geom.centroid) else 0.0
        return float(max(0.0, min(1.0, inter.area / geom.area)))
    except Exception:
        # Fallback to centroid test
        return 1.0 if land.contains(geom.centroid) else 0.0

