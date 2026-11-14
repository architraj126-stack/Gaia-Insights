"""
Spatial Region Masking and Area-Weighting Service (SPEC 14.2, Scientific Rule 6).

Responsibilities:
- Compute grid cell bounds and geodesic cell areas on the WGS84 sphere/ellipsoid.
- Compute fractional cell overlap with the target Shapely Polygon or MultiPolygon.
  (Falls back gracefully to cell-centre containment if fractional geometry operation fails).
- Compute area-weighted regional mean for each time step.
- Track valid cell count and valid area (km²) per time step, taking NaNs/fill values into account.
- Record masking method ('fractional_overlap' or 'cell_centre') and area weighting method ('geodesic_ellipsoid').
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import xarray as xr
from shapely.geometry import box, shape
from shapely.geometry.base import BaseGeometry

from backend.app.services.boundaries import is_point_on_land

logger = logging.getLogger(__name__)

# Earth volumetric mean radius in kilometers (IUGG WGS84)
EARTH_RADIUS_KM = 6371.0088


def compute_geodesic_cell_area_km2(lat_deg: float, dlat_deg: float, dlon_deg: float) -> float:
    """
    Computes exact spherical geodesic surface area in km² for a regular grid cell
    centered at lat_deg with height dlat_deg and width dlon_deg.
    Formula: R^2 * dlon_rad * |sin(lat2_rad) - sin(lat1_rad)|
    """
    lat1_rad = math.radians(lat_deg - (dlat_deg / 2.0))
    lat2_rad = math.radians(lat_deg + (dlat_deg / 2.0))
    dlon_rad = math.radians(dlon_deg)
    sin_diff = abs(math.sin(lat2_rad) - math.sin(lat1_rad))
    return (EARTH_RADIUS_KM**2) * dlon_rad * sin_diff


def build_grid_mask_weights(
    lats: np.ndarray,
    lons: np.ndarray,
    geom: BaseGeometry,
    method: str = "fractional_overlap",
    coverage_type: Optional[str] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    """
    For 1D arrays of lats and lons, computes:
    - weights: 2D array of (cell_area_km2 * overlap_fraction)
    - fractions: 2D array of overlap_fraction (0.0 to 1.0)
    - cell_areas: 2D array of cell_area_km2
    - chosen_method: string indicating method used
    """
    n_lats = len(lats)
    n_lons = len(lons)

    # Estimate grid spacing
    dlat = abs(float(lats[1] - lats[0])) if n_lats > 1 else 2.5
    dlon = abs(float(lons[1] - lons[0])) if n_lons > 1 else 2.5

    # 1D cell areas per latitude row
    row_areas = np.array(
        [compute_geodesic_cell_area_km2(float(lat), dlat, dlon) for lat in lats],
        dtype=np.float64,
    )
    # Broadcast to 2D (lat, lon)
    cell_areas_2d = np.tile(row_areas[:, np.newaxis], (1, n_lons))

    fractions_2d = np.zeros((n_lats, n_lons), dtype=np.float64)
    minx, miny, maxx, maxy = geom.bounds

    chosen_method = method

    for i, lat in enumerate(lats):
        cell_y0 = float(lat) - (dlat / 2.0)
        cell_y1 = float(lat) + (dlat / 2.0)

        # Quick bbox rejection on latitude
        if cell_y1 < miny or cell_y0 > maxy:
            continue

        cell_nominal_area = dlat * dlon

        for j, lon in enumerate(lons):
            cell_x0 = float(lon) - (dlon / 2.0)
            cell_x1 = float(lon) + (dlon / 2.0)

            # Quick bbox rejection on longitude
            if cell_x1 < minx or cell_x0 > maxx:
                continue

            cell_box = box(cell_x0, cell_y0, cell_x1, cell_y1)

            if not geom.intersects(cell_box):
                continue

            # Enforce coverage: land-only variables give no ocean values, ocean-only give no land values (SPEC 6.3)
            cell_center_lon = float(lon)
            cell_center_lat = float(lat)
            if coverage_type == "land_only" and not is_point_on_land(cell_center_lon, cell_center_lat):
                continue
            elif coverage_type == "ocean_only" and is_point_on_land(cell_center_lon, cell_center_lat):
                continue

            if geom.contains(cell_box):
                fractions_2d[i, j] = 1.0
            elif chosen_method == "fractional_overlap":
                try:
                    inter = cell_box.intersection(geom)
                    frac = inter.area / cell_nominal_area
                    fractions_2d[i, j] = max(0.0, min(1.0, frac))
                except Exception as e:
                    logger.warning("Fractional cell intersection failed at lat=%s, lon=%s: %s; falling back to cell centroid.", lat, lon, e)
                    fractions_2d[i, j] = 1.0 if geom.contains(cell_box.centroid) else 0.0
            else:
                fractions_2d[i, j] = 1.0 if geom.contains(cell_box.centroid) else 0.0

    weights_2d = cell_areas_2d * fractions_2d
    return weights_2d, fractions_2d, cell_areas_2d, chosen_method


def extract_regional_mean_timeseries(
    data_array: xr.DataArray,
    geom_dict_or_shape: Any,
    method: str = "fractional_overlap",
    coverage_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Masks the 3D data_array (time, lat, lon) with the given geometry.
    Computes area-weighted mean, valid cell counts, and valid area per time step.
    Enforces land/ocean coverage rules (SPEC 6.3).

    Returns:
    {
      "time_steps": list of ISO dates,
      "mean_values": list of floats (NaN where invalid/empty),
      "valid_cell_counts": list of ints,
      "valid_areas_km2": list of floats,
      "total_region_area_km2": float,
      "intersecting_cell_count": int,
      "mask_method": str,
      "area_weighting": "geodesic_ellipsoid",
      "status": "Available" | "Unavailable"
    }
    """
    geom = shape(geom_dict_or_shape) if isinstance(geom_dict_or_shape, dict) else geom_dict_or_shape

    lats = data_array["lat"].values
    lons = data_array["lon"].values

    weights_2d, fractions_2d, cell_areas_2d, chosen_method = build_grid_mask_weights(
        lats, lons, geom, method=method, coverage_type=coverage_type
    )

    intersecting_cells = int(np.sum(fractions_2d > 0.0))
    total_region_area_km2 = float(np.sum(weights_2d))

    if intersecting_cells == 0 or total_region_area_km2 <= 0.0:
        dlat = abs(float(lats[1] - lats[0])) if len(lats) > 1 else 2.5
        dlon = abs(float(lons[1] - lons[0])) if len(lons) > 1 else 2.5
        min_lat, max_lat = float(np.min(lats)), float(np.max(lats))
        min_lon, max_lon = float(np.min(lons)), float(np.max(lons))
        extent_with_buffer = box(
            min_lon - 1.5 * dlon,
            min_lat - 1.5 * dlat,
            max_lon + 1.5 * dlon,
            max_lat + 1.5 * dlat,
        )

        # SPEC 3.3 / Requirement 3: A disjoint region returns 0 valid cells and status Unavailable.
        # Fallback to nearest cell is strictly prohibited unless geometry is within one grid cell of the dataset extent.
        if not extent_with_buffer.intersects(geom):
            time_coords = [str(t)[:10] for t in data_array["time"].values]
            return {
                "time_steps": time_coords,
                "mean_values": [None] * len(time_coords),
                "valid_cell_counts": [0] * len(time_coords),
                "valid_areas_km2": [0.0] * len(time_coords),
                "total_region_area_km2": 0.0,
                "intersecting_cell_count": 0,
                "mask_method": "disjoint_unavailable",
                "area_weighting": "geodesic_ellipsoid",
                "status": "Unavailable",
                "warnings": ["Selected region is disjoint from dataset spatial extent (0 valid cells, status Unavailable)."],
            }

        centroid = geom.centroid
        target_lat = float(centroid.y)
        target_lon = float(centroid.x)

        # Only fallback if centroid matches coverage requirements
        is_allowed = True
        if coverage_type == "land_only" and not is_point_on_land(target_lon, target_lat):
            is_allowed = False
        elif coverage_type == "ocean_only" and is_point_on_land(target_lon, target_lat):
            is_allowed = False

        if is_allowed:
            lat_idx = int(np.argmin(np.abs(lats - target_lat)))
            lon_idx = int(np.argmin(np.abs(lons - target_lon)))

            weights_2d[lat_idx, lon_idx] = cell_areas_2d[lat_idx, lon_idx]
            fractions_2d[lat_idx, lon_idx] = 1.0
            chosen_method = "nearest_cell_fallback"
            intersecting_cells = 1
            total_region_area_km2 = float(cell_areas_2d[lat_idx, lon_idx])
        else:
            time_coords = [str(t)[:10] for t in data_array["time"].values]
            return {
                "time_steps": time_coords,
                "mean_values": [None] * len(time_coords),
                "valid_cell_counts": [0] * len(time_coords),
                "valid_areas_km2": [0.0] * len(time_coords),
                "total_region_area_km2": 0.0,
                "intersecting_cell_count": 0,
                "mask_method": "disjoint_unavailable",
                "area_weighting": "geodesic_ellipsoid",
                "status": "Unavailable",
                "warnings": ["Selected region has 0 valid cells matching dataset coverage type (status Unavailable)."],
            }

    # Convert 3D array values to numpy: shape (T, lat, lon)
    vals = data_array.values  # (T, Y, X)
    time_coords = [str(t)[:10] for t in data_array["time"].values]

    means: List[Optional[float]] = []
    valid_counts: List[int] = []
    valid_areas: List[float] = []

    # Broadcast weights to each time step
    for t_idx in range(len(time_coords)):
        step_vals = vals[t_idx]  # (Y, X)
        valid_mask = (~np.isnan(step_vals)) & (weights_2d > 0.0)

        step_valid_count = int(np.sum(valid_mask))
        valid_counts.append(step_valid_count)

        if step_valid_count == 0:
            means.append(None)
            valid_areas.append(0.0)
        else:
            step_weights = weights_2d[valid_mask]
            step_sum_weights = float(np.sum(step_weights))
            valid_areas.append(round(step_sum_weights, 2))

            if step_sum_weights > 0:
                weighted_sum = float(np.sum(step_vals[valid_mask] * step_weights))
                step_mean = weighted_sum / step_sum_weights
                means.append(round(step_mean, 6))
            else:
                means.append(None)

    return {
        "time_steps": time_coords,
        "mean_values": means,
        "valid_cell_counts": valid_counts,
        "valid_areas_km2": valid_areas,
        "total_region_area_km2": round(total_region_area_km2, 2),
        "intersecting_cell_count": intersecting_cells,
        "mask_method": chosen_method,
        "area_weighting": "geodesic_ellipsoid",
        "status": "Available" if intersecting_cells > 0 else "Unavailable",
    }
