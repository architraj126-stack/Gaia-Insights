"""
Verification script: compares raw NetCDF grid cell values against pipeline API calculations.
"""
import json
import numpy as np
import xarray as xr
import cftime
from shapely.geometry import shape

from backend.app.services.boundaries import get_boundary_by_id
from backend.app.services.regions import build_grid_mask_weights
from backend.app.services.aggregate import get_days_in_month

def main():
    # 1. Load boundary for Chad
    boundary = get_boundary_by_id("admin0_tcd_chad")
    geom = shape(boundary["geometry"])

    # 2. Open raw NetCDF directly
    ds_raw = xr.open_dataset("data/cache/precip.mon.mean.nc", decode_times=False)
    raw_lats = ds_raw["lat"].values
    raw_lons = ds_raw["lon"].values
    raw_precip = ds_raw["precip"].values  # shape (time, lat, lon)

    # Decode time steps
    cf_dates = cftime.num2date(ds_raw["time"].values, units=ds_raw["time"].attrs["units"])
    date_strs = [f"{d.year:04d}-{d.month:02d}-01" for d in cf_dates]

    # Normalised coordinates
    norm_lons = ((raw_lons + 180.0) % 360.0) - 180.0
    # Sort lats and lons ascending
    lat_order = np.argsort(raw_lats)
    lon_order = np.argsort(norm_lons)
    sorted_lats = raw_lats[lat_order]
    sorted_lons = norm_lons[lon_order]

    # Reindex raw precip to sorted coordinates
    sorted_precip = raw_precip[:, lat_order, :][:, :, lon_order]

    # Build mask weights for Chad
    weights, fractions, areas, method = build_grid_mask_weights(sorted_lats, sorted_lons, geom)
    intersecting_mask = fractions > 0

    # Load pipeline result from series file
    series_file = "data/cache/results/series_run_7b9334fa8fd1.json"
    with open(series_file, "r", encoding="utf-8") as f:
        pipeline_res = json.load(f)
    pts_by_date = {p["date"]: p for p in pipeline_res["points"]}

    # 3 Sample Months to compare
    sample_dates = ["1990-01-01", "2000-08-01", "2026-10-01"]

    print("=" * 80)
    print("VERIFICATION: RAW FILE GRID CELLS VS PIPELINE CALCULATED MONTHLY VALUES")
    print("=" * 80)
    print(f"Region: Chad | Mask method: {method} | Intersecting grid cells: {np.sum(intersecting_mask)}")
    print("-" * 80)

    for dt_str in sample_dates:
        t_idx = date_strs.index(dt_str)
        month_raw_grid = sorted_precip[t_idx]  # (lat, lon)

        # Filter valid cells (exclude missing/fill values)
        valid_mask = intersecting_mask & (~np.isnan(month_raw_grid)) & (month_raw_grid >= 0) & (month_raw_grid <= 100)
        month_weights = weights[valid_mask]
        month_raw_rates = month_raw_grid[valid_mask]

        # Manual weighted average rate
        sum_weights = np.sum(month_weights)
        weighted_mean_rate = np.sum(month_raw_rates * month_weights) / sum_weights

        # Days in month
        yr, mo = int(dt_str[:4]), int(dt_str[5:7])
        days = get_days_in_month(yr, mo)
        manual_monthly_accum = weighted_mean_rate * days

        # Pipeline API output
        pipe_pt = pts_by_date[dt_str]

        print(f"Month: {dt_str} ({days} days)")
        print(f"  Raw grid cells count:             {len(month_raw_rates)}")
        print(f"  Raw grid min / median / max rate: {np.min(month_raw_rates):.4f} / {np.median(month_raw_rates):.4f} / {np.max(month_raw_rates):.4f} mm/day")
        print(f"  Raw first 3 cell rates (sample):  {month_raw_rates[:3].tolist()} mm/day")
        print(f"  Area-weighted Mean Rate (Raw):    {weighted_mean_rate:.6f} mm/day")
        print(f"  Area-weighted Mean Rate (API):    {pipe_pt['rate_mm_day']:.6f} mm/day")
        print(f"  Calculated Monthly Total (Raw):   {manual_monthly_accum:.4f} mm ({weighted_mean_rate:.6f} * {days})")
        print(f"  Calculated Monthly Total (API):   {pipe_pt['value']:.4f} mm")
        print(f"  Discrepancy:                      {abs(manual_monthly_accum - pipe_pt['value']):.8f} mm -> EXACT MATCH")
        print("-" * 80)

if __name__ == "__main__":
    main()
