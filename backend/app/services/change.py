"""
Spatial Change Detection Service (SPEC 9, 14.5, 14.8, Scientific Rules 1, 2, 3, 6, 7, 8).

Key Responsibilities:
- Validate baseline and comparison periods against data availability and reject overlaps
  unless explicitly confirmed.
- Compute per-cell baseline value A and comparison value B with consistent aggregation rules
  (e.g., annual precipitation totals aggregated by days in month, then mean across years of period).
- Compute difference metrics:
  * Absolute change: B - A (in native units, e.g. mm/year).
  * Percentage change: 100 * (B - A) / |A| only where |A| > epsilon, else NaN with warning.
  * Spatial trend: per-cell OLS slope per year across the span, distinct from 2-period diff.
- Preserve NaNs everywhere: missing is never zero; no silent interpolation.
- Generate georeferenced GeoTIFF/COG via rioxarray.
- Generate transparent RGBA map overlay PNG for Leaflet and symmetric diverging colormap legend.
- Calculate spatial summary per SPEC 9.6: area-weighted mean change, share increasing/decreasing,
  min/max with coordinates, and no-data area reported separately from no-change.
"""
from __future__ import annotations

import calendar
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import xarray as xr
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from backend.app.config import settings
from backend.app.services.aggregate import get_days_in_month
from backend.app.services.regions import build_grid_mask_weights

logger = logging.getLogger("backend.services.change")

OUTPUTS_DIR = Path(settings.DATA_OUTPUTS_DIR)
if not OUTPUTS_DIR.is_absolute():
    OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / settings.DATA_OUTPUTS_DIR
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def validate_period_coverage(
    start_year: int,
    end_year: int,
    available_years: List[int],
    period_name: str = "period",
) -> None:
    """Validates that a period's years are in chronological order and within coverage."""
    if start_year > end_year:
        raise ValueError(f"{period_name.capitalize()} start year ({start_year}) cannot be greater than end year ({end_year}).")
    min_year = min(available_years)
    max_year = max(available_years)
    if start_year < min_year or end_year > max_year:
        raise ValueError(
            f"{period_name.capitalize()} [{start_year}, {end_year}] exceeds available coverage [{min_year}, {max_year}]."
        )


def check_periods_overlap(
    baseline_years: Tuple[int, int],
    comparison_years: Tuple[int, int],
    allow_overlap: bool = False,
) -> List[str]:
    """
    Checks if baseline and comparison periods overlap.
    Rejects overlapping periods unless allow_overlap is explicitly confirmed.
    """
    warnings: List[str] = []
    b_start, b_end = baseline_years
    c_start, c_end = comparison_years

    # Check overlap: start <= other_end and end >= other_start
    if max(b_start, c_start) <= min(b_end, c_end):
        msg = f"Baseline period [{b_start}-{b_end}] and comparison period [{c_start}-{c_end}] overlap."
        if not allow_overlap:
            raise ValueError(f"{msg} Overlapping periods must be explicitly confirmed.")
        else:
            warnings.append(f"Warning: {msg} Analysis proceeded under explicit confirmation.")
    return warnings


def compute_annual_cell_values(
    data_array: xr.DataArray,
    years: List[int],
    variable: str = "precipitation",
) -> np.ndarray:
    """
    Computes annual 2D values (shape: (len(years), n_lats, n_lons)) for each cell.
    For precipitation rates (mm/day):
      Accumulates each month by days in month; if any month of the 12 calendar months
      is missing or NaN for a cell, that cell's annual total for that year is NaN.
    For state variables (temperature):
      Computes the 12-month mean; if any month is missing, annual value is NaN.
    """
    lats = data_array["lat"].values
    lons = data_array["lon"].values
    n_years = len(years)
    n_lats = len(lats)
    n_lons = len(lons)

    annual_cubes = np.full((n_years, n_lats, n_lons), np.nan, dtype=np.float64)
    all_time_steps = set(str(t)[:10] for t in data_array["time"].values)

    for y_idx, year in enumerate(years):
        # Verify all 12 calendar months exist in dataset
        expected_months = [f"{year}-{m:02d}-01" for m in range(1, 13)]
        if not all(m_step in all_time_steps for m_step in expected_months):
            # Missing one or more months in dataset coverage -> Entire year is NaN
            continue

        monthly_slices = []
        month_days = []
        for m in range(1, 13):
            m_step = f"{year}-{m:02d}-01"
            da_m = data_array.sel(time=m_step).values.astype(np.float64)
            monthly_slices.append(da_m)
            month_days.append(get_days_in_month(year, m))

        # Stack to (12, lat, lon)
        stacked = np.stack(monthly_slices, axis=0)  # (12, n_lats, n_lons)

        if variable == "precipitation":
            # Days in month broadcast
            days_arr = np.array(month_days, dtype=np.float64)[:, np.newaxis, np.newaxis]
            # Accumulation per month
            accum = stacked * days_arr  # (12, n_lats, n_lons)
            # If any month has NaN at (i, j), sum across months is NaN
            has_nan = np.isnan(stacked).any(axis=0)
            annual_sum = np.sum(accum, axis=0)
            annual_sum[has_nan] = np.nan
            annual_cubes[y_idx] = annual_sum
        elif variable in ["land_surface_temperature", "temperature"]:
            has_nan = np.isnan(stacked).any(axis=0)
            annual_mean = np.mean(stacked, axis=0) - 273.15
            annual_mean[has_nan] = np.nan
            annual_cubes[y_idx] = annual_mean
        elif variable in ["humidity", "QV2M", "merra2_monthly_qv2m"]:
            has_nan = np.isnan(stacked).any(axis=0)
            annual_mean = np.mean(stacked, axis=0) * 1000.0
            annual_mean[has_nan] = np.nan
            annual_cubes[y_idx] = annual_mean
        else:
            has_nan = np.isnan(stacked).any(axis=0)
            annual_mean = np.mean(stacked, axis=0)
            annual_mean[has_nan] = np.nan
            annual_cubes[y_idx] = annual_mean

    return annual_cubes


def compute_period_mean_field(
    annual_cubes: np.ndarray,
) -> np.ndarray:
    """
    Computes temporal mean across the years for each cell (n_lats, n_lons).
    Requires at least one valid year; if all years are NaN, result is NaN.
    """
    # Use np.nanmean, but where all slices are NaN, np.nanmean issues warning and returns NaN
    with np.errstate(all="ignore"):
        all_nan = np.isnan(annual_cubes).all(axis=0)
        mean_field = np.nanmean(annual_cubes, axis=0)
        mean_field[all_nan] = np.nan
    return mean_field


def compute_spatial_trend_slope(
    annual_cubes: np.ndarray,
    years: List[int],
) -> np.ndarray:
    """
    Computes per-cell linear trend slope per year across the given years.
    If a cell has fewer than 3 valid annual observations, slope is NaN.
    """
    n_years, n_lats, n_lons = annual_cubes.shape
    slopes = np.full((n_lats, n_lons), np.nan, dtype=np.float64)
    x = np.array(years, dtype=np.float64)

    for i in range(n_lats):
        for j in range(n_lons):
            y = annual_cubes[:, i, j]
            valid = ~np.isnan(y)
            if np.sum(valid) >= 3:
                xv = x[valid]
                yv = y[valid]
                x_mean = np.mean(xv)
                y_mean = np.mean(yv)
                denom = np.sum((xv - x_mean) ** 2)
                if denom > 0:
                    slopes[i, j] = np.sum((xv - x_mean) * (yv - y_mean)) / denom

    return slopes


def rgb_to_hex(rgba: Tuple[float, float, float, float]) -> str:
    r = int(round(rgba[0] * 255))
    g = int(round(rgba[1] * 255))
    b = int(round(rgba[2] * 255))
    return f"#{r:02x}{g:02x}{b:02x}"


def generate_map_overlay_and_legend(
    diff_grid: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    fractions_2d: np.ndarray,
    run_id: str,
    units: str,
    output_dir: Path,
) -> Tuple[str, List[List[float]], Dict[str, Any]]:
    """
    Creates a transparent PNG map overlay and a symmetric diverging JSON legend.
    - NaNs and unselected region cells (fraction == 0) are rendered completely transparent.
    - Center is symmetric about zero [-M, +M].
    - Flips along latitude axis so North is at the top of the image for Leaflet.
    """
    masked_diff = diff_grid.copy()
    masked_diff[fractions_2d <= 0.0] = np.nan

    valid_vals = masked_diff[~np.isnan(masked_diff)]
    if len(valid_vals) > 0:
        max_abs = float(np.max(np.abs(valid_vals)))
        if max_abs <= 1e-6:
            max_abs = 1.0
    else:
        max_abs = 1.0

    # Symmetric range [-M, M]
    vmin = -max_abs
    vmax = max_abs

    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    # RdBu_r colormap: blue for negative, white/neutral for zero, red for positive (SPEC 9.5)
    cmap = plt.get_cmap("RdBu_r").copy()
    if hasattr(cmap, "with_extremes"):
        cmap = cmap.with_extremes(bad=(0.0, 0.0, 0.0, 0.0))
    else:
        cmap.set_bad(color=(0.0, 0.0, 0.0, 0.0))  # Transparent alpha for missing data

    # Image orientation: Leaflet expects row 0 to be North (highest latitude)
    # lats are ascending (south to north), so we flip vertically
    flipped_grid = np.flipud(masked_diff)
    rgba = cmap(norm(flipped_grid))

    # Save PNG overlay
    img_bytes = (rgba * 255).astype(np.uint8)
    img = Image.fromarray(img_bytes, mode="RGBA")
    overlay_filename = f"overlay_{run_id}.png"
    overlay_path = output_dir / overlay_filename
    img.save(overlay_path, format="PNG")

    # Calculate geographic bounds for Leaflet L.imageOverlay
    dlat = abs(float(lats[1] - lats[0])) if len(lats) > 1 else 2.5
    dlon = abs(float(lons[1] - lons[0])) if len(lons) > 1 else 2.5

    south = float(np.min(lats)) - (dlat / 2.0)
    north = float(np.max(lats)) + (dlat / 2.0)
    west = float(np.min(lons)) - (dlon / 2.0)
    east = float(np.max(lons)) + (dlon / 2.0)

    # Leaflet bounds: [[south, west], [north, east]]
    bounds = [[south, west], [north, east]]

    # Diverging symmetric legend
    thresholds = [
        round(vmin, 2),
        round(vmin / 2.0, 2),
        0.0,
        round(vmax / 2.0, 2),
        round(vmax, 2),
    ]
    colors = [rgb_to_hex(cmap(norm(t))) for t in thresholds]

    legend = {
        "colormap": "RdBu_r",
        "symmetric_zero": 0.0,
        "min_val": round(vmin, 3),
        "max_val": round(vmax, 3),
        "units": units,
        "thresholds": thresholds,
        "colors": colors,
        "no_data_swatch": {
            "color": "#9ca3af",
            "label": "No data / Outside study region",
        },
    }

    return f"/api/analysis/change-map/{run_id}/overlay.png", bounds, legend


def write_geotiff(
    diff_grid: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    run_id: str,
    output_dir: Path,
) -> Path:
    """
    Writes difference grid as a georeferenced GeoTIFF via rioxarray.
    """
    import rioxarray

    # Build DataArray with (lat, lon) coordinates
    # Sort lat descending (North to South) for standard raster transform
    lat_desc = np.sort(lats)[::-1]
    # Reindex grid to match lat descending
    if lats[0] < lats[-1]:
        reindexed_grid = np.flipud(diff_grid).astype(np.float32)
    else:
        reindexed_grid = diff_grid.astype(np.float32)

    da = xr.DataArray(
        reindexed_grid,
        coords=[("lat", lat_desc.astype(np.float64)), ("lon", lons.astype(np.float64))],
        name="change_difference",
    )
    da = da.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    da = da.rio.write_crs("EPSG:4326")
    da = da.rio.write_nodata(np.nan)

    geotiff_path = output_dir / f"change_{run_id}.tif"
    da.rio.to_raster(str(geotiff_path), driver="GTiff")
    return geotiff_path


def compute_spatial_summary(
    diff_grid: np.ndarray,
    weights_2d: np.ndarray,
    fractions_2d: np.ndarray,
    cell_areas_2d: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
) -> Dict[str, Any]:
    """
    Calculates spatial summary per SPEC 9.6:
    - Overall area-weighted mean change
    - Area share increasing (positive)
    - Area share decreasing (negative)
    - Area share no change (zero)
    - Highest change with location (lat, lon)
    - Lowest change with location (lat, lon)
    - No-data area reported separately from no-change area
    """
    region_mask = fractions_2d > 0.0
    total_region_area_km2 = float(np.sum(cell_areas_2d * fractions_2d))

    valid_mask = region_mask & (~np.isnan(diff_grid))
    valid_weights = weights_2d[valid_mask]
    valid_diffs = diff_grid[valid_mask]
    valid_area_km2 = float(np.sum(valid_weights))

    nodata_area_km2 = max(0.0, total_region_area_km2 - valid_area_km2)
    nodata_share_pct = (
        round((nodata_area_km2 / total_region_area_km2) * 100.0, 2)
        if total_region_area_km2 > 0
        else 0.0
    )

    if valid_area_km2 > 0.0 and len(valid_diffs) > 0:
        area_weighted_mean = float(np.sum(valid_diffs * valid_weights) / valid_area_km2)

        inc_mask = valid_diffs > 0.0
        dec_mask = valid_diffs < 0.0
        zero_mask = valid_diffs == 0.0

        inc_area = float(np.sum(valid_weights[inc_mask]))
        dec_area = float(np.sum(valid_weights[dec_mask]))
        zero_area = float(np.sum(valid_weights[zero_mask]))

        share_increasing_pct = round((inc_area / valid_area_km2) * 100.0, 2)
        share_decreasing_pct = round((dec_area / valid_area_km2) * 100.0, 2)
        share_no_change_pct = round((zero_area / valid_area_km2) * 100.0, 2)

        # Min and Max search over valid cells in region
        max_idx = np.argmax(valid_diffs)
        min_idx = np.argmin(valid_diffs)

        # Coordinate lookup
        valid_indices = np.argwhere(valid_mask)
        max_lat_idx, max_lon_idx = valid_indices[max_idx]
        min_lat_idx, min_lon_idx = valid_indices[min_idx]

        highest_change = {
            "value": round(float(valid_diffs[max_idx]), 4),
            "lat": round(float(lats[max_lat_idx]), 2),
            "lon": round(float(lons[max_lon_idx]), 2),
        }
        lowest_change = {
            "value": round(float(valid_diffs[min_idx]), 4),
            "lat": round(float(lats[min_lat_idx]), 2),
            "lon": round(float(lons[min_lon_idx]), 2),
        }
    else:
        area_weighted_mean = None
        share_increasing_pct = 0.0
        share_decreasing_pct = 0.0
        share_no_change_pct = 0.0
        highest_change = None
        lowest_change = None

    return {
        "area_weighted_mean_change": round(area_weighted_mean, 4) if area_weighted_mean is not None else None,
        "share_increasing_pct": share_increasing_pct,
        "share_decreasing_pct": share_decreasing_pct,
        "share_no_change_pct": share_no_change_pct,
        "highest_change": highest_change,
        "lowest_change": lowest_change,
        "valid_area_km2": round(valid_area_km2, 2),
        "total_region_area_km2": round(total_region_area_km2, 2),
        "nodata_area_km2": round(nodata_area_km2, 2),
        "nodata_share_pct": nodata_share_pct,
        "valid_cell_count": int(np.sum(valid_mask)),
        "intersecting_cell_count": int(np.sum(region_mask)),
    }


def execute_change_detection_analysis(
    data_array: xr.DataArray,
    geometry: BaseGeometry,
    baseline_years: Tuple[int, int],
    comparison_years: Tuple[int, int],
    variable: str = "precipitation",
    metric: str = "absolute",  # absolute | percentage | spatial_trend
    aggregation: str = "annual",
    epsilon: float = 1.0,
    allow_overlap: bool = False,
    run_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Executes complete end-to-end change detection analysis (SPEC 9 & 14.5).
    """
    if run_id is None:
        import uuid
        run_id = f"run_{uuid.uuid4().hex[:12]}"

    if output_dir is None:
        output_dir = OUTPUTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    warnings: List[str] = []

    # 1. Period checks
    all_years = sorted(list(set(int(str(t)[:4]) for t in data_array["time"].values)))
    validate_period_coverage(baseline_years[0], baseline_years[1], all_years, "baseline")
    validate_period_coverage(comparison_years[0], comparison_years[1], all_years, "comparison")

    overlap_warnings = check_periods_overlap(baseline_years, comparison_years, allow_overlap)
    warnings.extend(overlap_warnings)

    lats = data_array["lat"].values
    lons = data_array["lon"].values

    # 2. Geometry mask & weights
    weights_2d, fractions_2d, cell_areas_2d, chosen_method = build_grid_mask_weights(
        lats, lons, geometry, method="fractional_overlap"
    )

    if np.sum(fractions_2d > 0.0) == 0:
        dlat = abs(float(lats[1] - lats[0])) if len(lats) > 1 else 2.5
        dlon = abs(float(lons[1] - lons[0])) if len(lons) > 1 else 2.5
        min_lat, max_lat = float(np.min(lats)), float(np.max(lats))
        min_lon, max_lon = float(np.min(lons)), float(np.max(lons))
        from shapely.geometry import box
        extent_with_buffer = box(
            min_lon - 1.5 * dlon,
            min_lat - 1.5 * dlat,
            max_lon + 1.5 * dlon,
            max_lat + 1.5 * dlat,
        )
        if not extent_with_buffer.intersects(geometry):
            raise ValueError("Selected region is disjoint from dataset spatial extent (0 valid cells, status Unavailable).")

        # Fallback to nearest grid cell centroid only if geometry is within one grid cell of dataset extent
        centroid = geometry.centroid
        lat_idx = int(np.argmin(np.abs(lats - float(centroid.y))))
        lon_idx = int(np.argmin(np.abs(lons - float(centroid.x))))
        fractions_2d[lat_idx, lon_idx] = 1.0
        weights_2d[lat_idx, lon_idx] = cell_areas_2d[lat_idx, lon_idx]
        chosen_method = "nearest_cell_fallback"
        warnings.append("Study region smaller than grid cell resolution; used nearest grid cell within extent buffer.")

    # 3. Compute per-cell values for baseline and comparison periods
    baseline_year_list = list(range(baseline_years[0], baseline_years[1] + 1))
    comp_year_list = list(range(comparison_years[0], comparison_years[1] + 1))

    if aggregation == "annual":
        b_cubes = compute_annual_cell_values(data_array, baseline_year_list, variable=variable)
        c_cubes = compute_annual_cell_values(data_array, comp_year_list, variable=variable)
        A = compute_period_mean_field(b_cubes)
        B = compute_period_mean_field(c_cubes)
        if variable == "precipitation":
            native_units = "mm/year"
        elif variable in ["land_surface_temperature", "temperature", "sea_surface_temperature", "sst"]:
            native_units = "°C"
        elif variable in ["soil_moisture", "SoilMoi0_10cm_inst", "gldas_noah025_m_v21"]:
            native_units = "kg/m²"
        elif variable in ["humidity", "QV2M", "merra2_monthly_qv2m"]:
            native_units = "g/kg"
        else:
            native_units = "native"
    elif aggregation == "monthly":
        # Monthly mean rate
        b_steps = [str(t)[:10] for t in data_array["time"].values if baseline_years[0] <= int(str(t)[:4]) <= baseline_years[1]]
        c_steps = [str(t)[:10] for t in data_array["time"].values if comparison_years[0] <= int(str(t)[:4]) <= comparison_years[1]]
        with np.errstate(all="ignore"):
            A = np.nanmean(data_array.sel(time=b_steps).values, axis=0)
            B = np.nanmean(data_array.sel(time=c_steps).values, axis=0)
        if variable == "precipitation":
            native_units = "mm/day"
        elif variable in ["land_surface_temperature", "temperature"]:
            A = A - 273.15
            B = B - 273.15
            native_units = "°C"
        elif variable in ["sea_surface_temperature", "sst"]:
            native_units = "°C"
        elif variable in ["soil_moisture", "SoilMoi0_10cm_inst", "gldas_noah025_m_v21"]:
            native_units = "kg/m²"
        elif variable in ["humidity", "QV2M", "merra2_monthly_qv2m"]:
            A = A * 1000.0
            B = B * 1000.0
            native_units = "g/kg"
        else:
            native_units = "native"
    else:
        raise ValueError(f"Unsupported aggregation: {aggregation}")

    # 4. Metric calculation
    if metric == "absolute":
        diff_grid = B - A
        units = native_units
        formula = "B - A (Comparison mean minus Baseline mean)"
    elif metric == "percentage":
        diff_grid = np.full_like(A, np.nan, dtype=np.float64)
        abs_A = np.abs(A)
        meaningful_mask = (abs_A > epsilon) & (~np.isnan(A)) & (~np.isnan(B))
        suppressed_cells = int(np.sum((abs_A <= epsilon) & (fractions_2d > 0.0) & (~np.isnan(A))))
        if suppressed_cells > 0:
            warnings.append(
                f"Percentage change suppressed for {suppressed_cells} cell(s) with baseline |A| <= {epsilon} {native_units}."
            )
        diff_grid[meaningful_mask] = 100.0 * (B[meaningful_mask] - A[meaningful_mask]) / abs_A[meaningful_mask]
        units = "%"
        formula = "100 * (B - A) / |A| where |A| > epsilon"
    elif metric == "spatial_trend":
        # Spatial trend slope across full span
        full_years = list(range(min(baseline_years[0], comparison_years[0]), max(baseline_years[1], comparison_years[1]) + 1))
        all_cubes = compute_annual_cell_values(data_array, full_years, variable=variable)
        diff_grid = compute_spatial_trend_slope(all_cubes, full_years)
        units = f"{native_units}/year"
        formula = "Per-cell ordinary least squares slope per year across span"
    else:
        raise ValueError(f"Unsupported metric: {metric}")

    # 5. Spatial summary (SPEC 9.6)
    summary = compute_spatial_summary(
        diff_grid=diff_grid,
        weights_2d=weights_2d,
        fractions_2d=fractions_2d,
        cell_areas_2d=cell_areas_2d,
        lats=lats,
        lons=lons,
    )

    # 6. Georeferenced GeoTIFF
    geotiff_path = write_geotiff(
        diff_grid=diff_grid,
        lats=lats,
        lons=lons,
        run_id=run_id,
        output_dir=output_dir,
    )

    # 7. Map overlay and legend
    overlay_url, bounds, legend = generate_map_overlay_and_legend(
        diff_grid=diff_grid,
        lats=lats,
        lons=lons,
        fractions_2d=fractions_2d,
        run_id=run_id,
        units=units,
        output_dir=output_dir,
    )

    # Cache run matrices for inspection
    cache_data = {
        "run_id": run_id,
        "lats": lats.tolist(),
        "lons": lons.tolist(),
        "baseline_mean": A.tolist(),
        "comparison_mean": B.tolist(),
        "diff_grid": diff_grid.tolist(),
        "fractions": fractions_2d.tolist(),
        "metric": metric,
        "units": units,
    }
    inspect_cache_file = output_dir / f"inspect_{run_id}.json"
    with open(inspect_cache_file, "w", encoding="utf-8") as f:
        json.dump(cache_data, f)

    is_merra2 = variable in ["land_surface_temperature", "temperature", "TS"]
    is_oisst = variable in ["sea_surface_temperature", "sst", "noaa_oisst_v21"]
    is_gldas = variable in ["soil_moisture", "SoilMoi0_10cm_inst", "gldas_noah025_m_v21"]
    is_humidity = variable in ["humidity", "QV2M", "merra2_monthly_qv2m"]
    if is_merra2:
        ds_id = "merra2_monthly_ts"
        ds_version = "5.12.4"
    elif is_oisst:
        ds_id = "noaa_oisst_v21"
        ds_version = "v2.1"
    elif is_gldas:
        ds_id = "gldas_noah025_m_v21"
        ds_version = "2.1"
    elif is_humidity:
        ds_id = "merra2_monthly_qv2m"
        ds_version = "5.12.4"
    else:
        ds_id = "gpcp_monthly_v23"
        ds_version = "v2.3"

    provenance = {
        "run_id": run_id,
        "dataset_id": ds_id,
        "dataset_version": ds_version,
        "variable": variable,
        "baseline_period": f"{baseline_years[0]}-{baseline_years[1]}",
        "comparison_period": f"{comparison_years[0]}-{comparison_years[1]}",
        "metric": metric,
        "aggregation": aggregation,
        "formula": formula,
        "units": units,
        "native_units": native_units,
        "mask_method": chosen_method,
        "area_weighting": "geodesic_ellipsoid",
        "geotiff_path": str(geotiff_path.resolve()),
        "output_format": "GeoTIFF/COG + Leaflet PNG overlay",
    }

    return {
        "run_id": run_id,
        "overlay_url": overlay_url,
        "bounds": bounds,
        "legend": legend,
        "spatial_summary": summary,
        "provenance": provenance,
        "warnings": warnings,
        "units": units,
        "metric": metric,
    }


def inspect_change_cell(
    run_id: str,
    target_lat: float,
    target_lon: float,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Inspects a single grid cell given lat/lon for a completed change detection run.
    """
    if output_dir is None:
        output_dir = OUTPUTS_DIR

    cache_file = output_dir / f"inspect_{run_id}.json"
    if not cache_file.exists():
        raise FileNotFoundError(f"Run output inspect file not found for run_id: {run_id}")

    with open(cache_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    lats = np.array(data["lats"])
    lons = np.array(data["lons"])
    A = np.array(data["baseline_mean"])
    B = np.array(data["comparison_mean"])
    diff = np.array(data["diff_grid"])
    fractions = np.array(data["fractions"])

    # Normalise target_lon to [-180, 180]
    norm_lon = ((target_lon + 180.0) % 360.0) - 180.0

    lat_idx = int(np.argmin(np.abs(lats - target_lat)))
    lon_idx = int(np.argmin(np.abs(lons - norm_lon)))

    cell_lat = float(lats[lat_idx])
    cell_lon = float(lons[lon_idx])
    b_val = float(A[lat_idx, lon_idx]) if not np.isnan(A[lat_idx, lon_idx]) else None
    c_val = float(B[lat_idx, lon_idx]) if not np.isnan(B[lat_idx, lon_idx]) else None
    d_val = float(diff[lat_idx, lon_idx]) if not np.isnan(diff[lat_idx, lon_idx]) else None
    fraction = float(fractions[lat_idx, lon_idx])

    return {
        "run_id": run_id,
        "requested_lat": target_lat,
        "requested_lon": target_lon,
        "cell_lat": cell_lat,
        "cell_lon": cell_lon,
        "baseline_mean": round(b_val, 4) if b_val is not None else None,
        "comparison_mean": round(c_val, 4) if c_val is not None else None,
        "difference": round(d_val, 4) if d_val is not None else None,
        "overlap_fraction": round(fraction, 4),
        "is_valid": d_val is not None and fraction > 0.0,
        "units": data.get("units", "mm/year"),
        "metric": data.get("metric", "absolute"),
    }
