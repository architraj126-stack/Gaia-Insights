import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional
import numpy as np
from shapely.geometry import Point, box, shape

from backend.app.api.catalog import load_catalog_seed
from backend.app.services.geometry import validate_and_normalize_geometry
from backend.app.services.boundaries import calculate_geometry_land_ratio

logger = logging.getLogger(__name__)

UNINGESTED_DATASET_IDS = set()


def parse_iso_date(date_str: str) -> Optional[datetime]:
    try:
        # Handle YYYY-MM-DD or YYYY-MM
        parts = date_str.strip().split("-")
        if len(parts) == 1:
            return datetime(int(parts[0]), 1, 1)
        elif len(parts) == 2:
            return datetime(int(parts[0]), int(parts[1]), 1)
        return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception as e:
        logger.error("Failed to parse ISO date '%s': %s", date_str, e)
        return None


def count_grid_cell_centers(geom: Any, grid_dx: float = 2.5, grid_dy: float = 2.5) -> int:
    """
    Counts how many regular grid cell centres fall inside the given geometry.
    Grid centres are aligned to half-cell offsets (e.g. -88.75 to +88.75, -178.75 to +178.75).
    """
    minx, miny, maxx, maxy = geom.bounds

    # Handle antimeridian wrap if bounds span across
    # Generate candidate grid lines covering the bounding box
    start_x = math.floor((minx - (grid_dx / 2.0)) / grid_dx) * grid_dx + (grid_dx / 2.0)
    end_x = math.ceil((maxx + (grid_dx / 2.0)) / grid_dx) * grid_dx + (grid_dx / 2.0)
    cand_lons = np.arange(start_x, end_x + 0.001, grid_dx)

    start_y = max(-90.0 + (grid_dy / 2.0), math.floor((miny - (grid_dy / 2.0)) / grid_dy) * grid_dy + (grid_dy / 2.0))
    end_y = min(90.0 - (grid_dy / 2.0), math.ceil((maxy + (grid_dy / 2.0)) / grid_dy) * grid_dy + (grid_dy / 2.0))
    cand_lats = np.arange(start_y, end_y + 0.001, grid_dy)

    count = 0
    # Test candidates within bounding box
    for x in cand_lons:
        if x > 180.0:
            x -= 360.0
        elif x < -180.0:
            x += 360.0
        for y in cand_lats:
            if miny <= y <= maxy:
                p = Point(x, y)
                if geom.contains(p):
                    count += 1
    return count


def check_dataset_availability(
    dataset_id: str,
    geometry: Optional[Dict[str, Any]] = None,
    bbox: Optional[List[float]] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates dataset availability against spatial region and temporal extent.
    Returns status ('Available' | 'Partial' | 'Unavailable'), coverage metrics,
    grid cell counts, and scientific warnings.
    """
    # 1. Lookup dataset in catalog
    variables = load_catalog_seed()
    target_dataset = None
    target_variable = None
    for var in variables:
        for ds in var.datasets:
            if ds.id == dataset_id:
                target_dataset = ds
                target_variable = var
                break
        if target_dataset:
            break

    if not target_dataset:
        raise ValueError(f"Dataset '{dataset_id}' not found in catalog.")

    if target_dataset.id in UNINGESTED_DATASET_IDS or target_dataset.status.startswith("Unavailable"):
        return {
            "dataset_id": target_dataset.id,
            "variable_id": target_dataset.variable_id,
            "product_name": target_dataset.product_name,
            "version": target_dataset.version,
            "status": "Unavailable - real data not yet ingested",
            "spatial_coverage_percent": 0.0,
            "temporal_coverage_percent": 0.0,
            "cell_count": 0,
            "spatial_resolution": target_dataset.spatial_resolution,
            "temporal_resolution": target_dataset.temporal_resolution,
            "area_km2": 0.0,
            "valid_date_range": {
                "start": target_dataset.start_date,
                "latest_observation_date": None,
                "last_catalogue_check": None,
            },
            "warnings": ["Unavailable - real data not yet ingested"],
            "provider": target_dataset.provider,
            "citation": target_dataset.citation,
        }

    warnings: List[str] = []

    # 2. Resolve and validate geometry
    validated_geom = None
    area_km2 = 0.0
    cell_count = 0
    spatial_coverage_pct = 100.0

    if bbox and not geometry:
        minx, miny, maxx, maxy = bbox
        geometry = {"type": "Polygon", "coordinates": [[[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]]}

    if geometry:
        val_res = validate_and_normalize_geometry(geometry=geometry)
        geom_obj = shape(val_res["geometry"])
        validated_geom = val_res["geometry"]
        area_km2 = val_res["area_km2"]
        warnings.extend(val_res["warnings"])

        # Estimate cell size at centroid latitude
        centroid_lat = val_res["centroid"][1]
        grid_dx = target_dataset.cell_dimensions[0] if target_dataset.cell_dimensions else 2.5
        grid_dy = target_dataset.cell_dimensions[1] if target_dataset.cell_dimensions else 2.5

        # Approx cell area at centroid latitude in km²
        cell_width_km = grid_dx * 111.32 * math.cos(math.radians(centroid_lat))
        cell_height_km = grid_dy * 110.57
        cell_area_km2 = abs(cell_width_km * cell_height_km)

        # Count grid cell centres
        cell_count = count_grid_cell_centers(geom_obj, grid_dx, grid_dy)

        # Check for tiny polygon compared to coarse cell
        if area_km2 < 0.5 * cell_area_km2:
            warnings.append(
                f"Selected region ({area_km2:,.1f} km²) is significantly smaller than one grid cell "
                f"(~{int(cell_area_km2):,} km² at latitude {centroid_lat:.1f}°). "
                f"Regional analysis will sample the single containing {grid_dx}° grid cell."
            )

        if cell_count == 0:
            warnings.append(
                f"Selected region contains 0 grid cell centres at {grid_dx}° × {grid_dy}° resolution; "
                f"nearest-neighbour sampling or fractional grid intersection will be applied."
            )
        elif cell_count < 4:
            warnings.append(
                f"Selected region contains only {cell_count} grid cell centre(s); "
                f"spatial variance and FDR significance cannot be reliably computed."
            )

        # Domain coverage check: land-only vs ocean-only vs global (SPEC 6.3, SPEC 14.1)
        coverage_type = "global"
        spatial_cov_str = (target_dataset.spatial_coverage or "").lower()
        if "land-only" in spatial_cov_str or target_dataset.variable_id in ["land_surface_temperature", "soil_moisture"]:
            coverage_type = "land_only"
        elif "ocean-only" in spatial_cov_str or target_dataset.variable_id in ["sea_surface_temperature"]:
            coverage_type = "ocean_only"

        var_label = target_variable.name if target_variable else target_dataset.product_name
        if coverage_type == "land_only":
            land_ratio = calculate_geometry_land_ratio(geom_obj)
            spatial_coverage_pct = round(land_ratio * 100.0, 1)
            if spatial_coverage_pct <= 0.001:
                spatial_coverage_pct = 0.0
                warnings.append(
                    f"Selected region has 0% land coverage. {var_label} "
                    f"is a land-only variable; no observations are available in ocean areas."
                )
            elif spatial_coverage_pct < 99.5:
                warnings.append(
                    f"Selected region has partial land coverage ({spatial_coverage_pct:.1f}% land). "
                    f"{var_label} is a land-only variable; ocean areas will contain no data."
                )
            else:
                spatial_coverage_pct = 100.0
        elif coverage_type == "ocean_only":
            land_ratio = calculate_geometry_land_ratio(geom_obj)
            ocean_ratio = 1.0 - land_ratio
            spatial_coverage_pct = round(ocean_ratio * 100.0, 1)
            if spatial_coverage_pct <= 0.001:
                spatial_coverage_pct = 0.0
                warnings.append(
                    f"Selected region has 0% ocean coverage. {var_label} "
                    f"is an ocean-only variable; no observations are available over land."
                )
            elif spatial_coverage_pct < 99.5:
                warnings.append(
                    f"Selected region has partial ocean coverage ({spatial_coverage_pct:.1f}% ocean). "
                    f"{var_label} is an ocean-only variable; land areas will contain no data."
                )
            else:
                spatial_coverage_pct = 100.0

    # 3. Temporal coverage check
    temporal_coverage_pct = 100.0
    req_start_dt = parse_iso_date(start) if start else None
    req_end_dt = parse_iso_date(end) if end else None
    ds_start_dt = parse_iso_date(target_dataset.start_date)

    if req_start_dt and ds_start_dt and req_start_dt < ds_start_dt:
        warnings.append(
            f"Requested start date ({start}) precedes dataset start date ({target_dataset.start_date}). "
            f"Historical observations are unavailable prior to {target_dataset.start_date}."
        )
        if req_end_dt and req_end_dt < ds_start_dt:
            temporal_coverage_pct = 0.0
        else:
            temporal_coverage_pct = 75.0  # partial temporal coverage

    # 4. Overall status determination
    if spatial_coverage_pct == 0.0 or temporal_coverage_pct == 0.0:
        overall_status = "Unavailable"
    elif spatial_coverage_pct < 100.0 or temporal_coverage_pct < 100.0:
        overall_status = "Partial"
    else:
        overall_status = "Available"

    # Phase 3a: use the real latest_observation_date from DB via the catalog model
    lat_obs_date = getattr(target_dataset, "latest_observation_date", None)
    last_check = getattr(target_dataset, "last_catalogue_check", None)

    return {
        "dataset_id": target_dataset.id,
        "variable_id": target_dataset.variable_id,
        "product_name": target_dataset.product_name,
        "version": target_dataset.version,
        "status": overall_status,
        "spatial_coverage_percent": spatial_coverage_pct,
        "temporal_coverage_percent": temporal_coverage_pct,
        "cell_count": cell_count,
        "spatial_resolution": target_dataset.spatial_resolution,
        "temporal_resolution": target_dataset.temporal_resolution,
        "area_km2": area_km2,
        "valid_date_range": {
            "start": target_dataset.start_date,
            "latest_observation_date": lat_obs_date,
            "last_catalogue_check": last_check,
        },
        "warnings": warnings,
        "provider": target_dataset.provider,
        "citation": target_dataset.citation,
    }
