import logging
from typing import Any, Dict, List, Optional, Tuple
import pyproj
import shapely
import shapely.affinity
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiPolygon,
    Point,
    Polygon,
    mapping,
    shape,
)
from shapely.ops import split, transform
from shapely.validation import make_valid

logger = logging.getLogger(__name__)

WGS84_GEOD = pyproj.Geod(ellps="WGS84")


def create_geodesic_buffer(lon: float, lat: float, radius_km: float, num_points: int = 72) -> Polygon:
    """
    Constructs an accurate geodesic buffer polygon on the WGS84 ellipsoid around (lon, lat).
    """
    radius_m = radius_km * 1000.0
    azimuths = [i * (360.0 / num_points) for i in range(num_points)]
    lons, lats, _ = WGS84_GEOD.fwd([lon] * num_points, [lat] * num_points, azimuths, [radius_m] * num_points)
    coords = list(zip(lons, lats))
    coords.append(coords[0])
    return Polygon(coords)


def reproject_to_wgs84(geom: shapely.geometry.base.BaseGeometry, from_crs: str) -> Tuple[shapely.geometry.base.BaseGeometry, Optional[str]]:
    """
    Reprojects geometry from `from_crs` into EPSG:4326 if not already in WGS84.
    """
    norm_crs = from_crs.strip().upper()
    if norm_crs in ["EPSG:4326", "WGS84", "CRS84", "URN:OGC:DEF:CRS:OGC:1.3:CRS84"]:
        return geom, None

    try:
        transformer = pyproj.Transformer.from_crs(from_crs, "EPSG:4326", always_xy=True)
        transformed = transform(transformer.transform, geom)
        return transformed, f"Geometry reprojected from {from_crs} to EPSG:4326."
    except Exception as e:
        logger.warning("Failed to reproject from %s: %s", from_crs, e)
        return geom, f"Warning: Could not reproject from {from_crs} ({e}). Assuming coordinates are WGS84."


def normalize_antimeridian_and_longitudes(
    geom: shapely.geometry.base.BaseGeometry,
) -> Tuple[shapely.geometry.base.BaseGeometry, List[str]]:
    """
    Detects and repairs geometries that cross the antimeridian (180°/-180°) or have longitudes
    outside [-180, 180]. Unwraps crossing rings, cuts at +/-180°, and normalizes longitudes into [-180, 180].
    """
    warnings: List[str] = []

    if isinstance(geom, Polygon):
        polys = [geom]
    elif isinstance(geom, MultiPolygon):
        polys = list(geom.geoms)
    else:
        return geom, warnings

    new_polys: List[Polygon] = []
    antimeridian_crossing = False
    coords_normalized = False

    for poly in polys:
        if poly.is_empty:
            continue
        ext_coords = list(poly.exterior.coords)

        # 1. Check if polygon wraps across 180 (adjacent longitudes differ by > 180)
        jump_detected = False
        for i in range(len(ext_coords) - 1):
            if abs(ext_coords[i + 1][0] - ext_coords[i][0]) > 180.0:
                jump_detected = True
                break

        # 2. Check if any longitude is outside [-180, 180]
        has_out_of_range = any(c[0] > 180.0 or c[0] < -180.0 for c in ext_coords)

        if jump_detected or has_out_of_range:
            antimeridian_crossing = True
            # Unwrap exterior coordinates into a continuous longitude strip
            unwrapped_ext: List[Tuple[float, float]] = []
            for i, (lon, lat) in enumerate(ext_coords):
                if i == 0:
                    # Bring first point close to canonical if wildly outside
                    norm_lon = ((lon + 180.0) % 360.0) - 180.0 if (lon > 360 or lon < -360) else lon
                    unwrapped_ext.append((norm_lon, lat))
                else:
                    prev_lon = unwrapped_ext[-1][0]
                    dlon = lon - prev_lon
                    while dlon > 180.0:
                        lon -= 360.0
                        dlon = lon - prev_lon
                    while dlon < -180.0:
                        lon += 360.0
                        dlon = lon - prev_lon
                    unwrapped_ext.append((lon, lat))

            # Unwrap interior holes similarly if present
            unwrapped_holes = []
            for hole in poly.interiors:
                hole_coords = list(hole.coords)
                unwrapped_hole: List[Tuple[float, float]] = []
                for i, (lon, lat) in enumerate(hole_coords):
                    if i == 0:
                        unwrapped_hole.append((lon, lat))
                    else:
                        prev_lon = unwrapped_hole[-1][0]
                        dlon = lon - prev_lon
                        while dlon > 180.0:
                            lon -= 360.0
                            dlon = lon - prev_lon
                        while dlon < -180.0:
                            lon += 360.0
                            dlon = lon - prev_lon
                        unwrapped_hole.append((lon, lat))
                unwrapped_holes.append(unwrapped_hole)

            p_unwrapped = Polygon(unwrapped_ext, unwrapped_holes)
            if not p_unwrapped.is_valid:
                p_unwrapped = make_valid(p_unwrapped)

            # Determine where to split (multiples of 180)
            minx, _, maxx, _ = p_unwrapped.bounds
            split_meridians = []
            # Find all meridian boundaries within [minx, maxx]
            k_min = int(minx // 180)
            k_max = int(maxx // 180) + 1
            for k in range(k_min, k_max + 1):
                meridian_x = k * 180.0
                if minx < meridian_x < maxx and (k % 2 != 0):  # odd multiples are antimeridians
                    split_meridians.append(meridian_x)

            parts = [p_unwrapped]
            for mx in split_meridians:
                splitter = LineString([(mx, -90.0), (mx, 90.0)])
                next_parts = []
                for p in parts:
                    split_res = split(p, splitter)
                    sub_geoms = split_res.geoms if hasattr(split_res, "geoms") else [split_res]
                    for sg in sub_geoms:
                        if isinstance(sg, Polygon) and not sg.is_empty:
                            next_parts.append(sg)
                        elif isinstance(sg, MultiPolygon):
                            next_parts.extend([g for g in sg.geoms if not g.is_empty])
                parts = next_parts

            # Shift every part back into standard WGS84 range [-180, 180]
            for part in parts:
                cx = part.centroid.x
                if cx > 180.0:
                    shift = -360.0 * (((cx + 180.0) // 360.0))
                    part = shapely.affinity.translate(part, xoff=shift)
                    coords_normalized = True
                elif cx < -180.0:
                    shift = 360.0 * (((-cx + 180.0) // 360.0))
                    part = shapely.affinity.translate(part, xoff=shift)
                    coords_normalized = True
                new_polys.append(part)
        else:
            new_polys.append(poly)

    if antimeridian_crossing:
        warnings.append("Geometry crosses the antimeridian (180°/-180°) and was split into a MultiPolygon.")
    elif coords_normalized:
        warnings.append("Longitudes outside standard [-180, 180] were normalized.")

    if not new_polys:
        return geom, warnings

    if len(new_polys) == 1:
        return new_polys[0], warnings
    return MultiPolygon(new_polys), warnings


def validate_and_normalize_geometry(
    geometry: Optional[Dict[str, Any]] = None,
    crs: str = "EPSG:4326",
    point: Optional[List[float]] = None,
    radius_km: Optional[float] = None,
    radius_m: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Validates, repairs, normalizes, and computes spatial metrics for an input geometry.
    Supports point + buffer calculation, GeoJSON repairs via make_valid, antimeridian splitting,
    and geodesic area calculation in km² via pyproj.
    """
    warnings: List[str] = []

    # 1. Point + Buffer conversion
    if point is not None:
        if radius_km is None and radius_m is not None:
            radius_km = radius_m / 1000.0
        elif radius_km is None:
            radius_km = 50.0  # default 50km if unspecified

        lon, lat = point[0], point[1]
        geom = create_geodesic_buffer(lon, lat, radius_km)
        warnings.append(f"Generated geodesic buffer polygon with radius {radius_km:.1f} km around ({lon:.4f}, {lat:.4f}).")
    elif geometry:
        # Check if geometry is a Feature or Geometry
        geom_dict = geometry.get("geometry", geometry) if isinstance(geometry, dict) else geometry
        
        # Check if geometry is a Point with radius
        if geom_dict.get("type") == "Point" and (radius_km is not None or radius_m is not None):
            coords = geom_dict.get("coordinates", [0, 0])
            r_km = radius_km if radius_km is not None else (radius_m / 1000.0)  # type: ignore
            geom = create_geodesic_buffer(coords[0], coords[1], r_km)
            warnings.append(f"Point geometry converted to geodesic buffer with radius {r_km:.1f} km.")
        else:
            try:
                geom = shape(geom_dict)
            except Exception as e:
                raise ValueError(f"Invalid GeoJSON geometry representation: {e}")
    else:
        raise ValueError("Either 'geometry' or 'point' with radius must be provided.")

    if geom.is_empty:
        raise ValueError("Geometry is empty.")

    # 2. CRS Reprojection if needed
    if crs and crs.strip().upper() not in ["EPSG:4326", "WGS84", "CRS84"]:
        geom, crs_warn = reproject_to_wgs84(geom, crs)
        if crs_warn:
            warnings.append(crs_warn)

    # 3. Validation and Repair via make_valid
    if not geom.is_valid:
        repaired = make_valid(geom)
        warnings.append("Geometry was invalid (e.g. self-intersecting) and has been repaired using make_valid.")
        
        # Extract 2D polygonal geometry from repaired result
        if isinstance(repaired, GeometryCollection):
            polys = []
            for g in repaired.geoms:
                if isinstance(g, Polygon) and not g.is_empty:
                    polys.append(g)
                elif isinstance(g, MultiPolygon) and not g.is_empty:
                    polys.extend(g.geoms)
            if not polys:
                raise ValueError("Repaired geometry does not contain any valid polygonal components.")
            geom = MultiPolygon(polys) if len(polys) > 1 else polys[0]
        else:
            geom = repaired

    # 4. Longitude and Antimeridian Normalization
    geom, anti_warns = normalize_antimeridian_and_longitudes(geom)
    warnings.extend(anti_warns)

    # Final validity verification
    if not geom.is_valid:
        geom = make_valid(geom)

    # 5. Geodesic Area Calculation via pyproj.Geod
    try:
        area_m2, perimeter_m = WGS84_GEOD.geometry_area_perimeter(geom)
        area_km2 = round(abs(area_m2) / 1_000_000.0, 3)
    except Exception as e:
        logger.error("Failed to compute geodesic area: %s", e)
        area_km2 = 0.0
        warnings.append(f"Geodesic area computation warning: {e}")

    # 6. BBox and Centroid
    minx, miny, maxx, maxy = geom.bounds
    bbox = [round(minx, 5), round(miny, 5), round(maxx, 5), round(maxy, 5)]
    centroid = [round(geom.centroid.x, 5), round(geom.centroid.y, 5)]

    return {
        "status": "valid",
        "crs": "EPSG:4326",
        "geometry": mapping(geom),
        "area_km2": area_km2,
        "bbox": bbox,
        "centroid": centroid,
        "warnings": warnings,
    }
