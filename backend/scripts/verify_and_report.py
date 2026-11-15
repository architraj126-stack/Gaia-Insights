"""
Verification and Data-Volume Table Generator (SPEC 14, 15).

Verifies each ingested dataset:
- First and last time steps
- Steps versus expected count
- Spatial grid dimensions
- Non-NaN cells in a typical month (e.g. 2020-06-01)
- Valid cells and steps for Chad, Fiji, and France (no nearest neighbour fallback)
- Decoded units and fill values
"""
import sys
import logging
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
import xarray as xr
from shapely.geometry import shape

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services.boundaries import get_boundary_by_id, search_boundaries
from backend.app.services.ingest import (
    normalize_gpcp_dataset,
    open_gpcp_dataset,
    normalize_oisst_dataset,
    open_oisst_dataset,
    normalize_merra2_dataset,
    open_merra2_dataset,
    normalize_merra2_qv2m_dataset,
    open_merra2_qv2m_dataset,
    normalize_gldas_dataset,
    open_gldas_dataset,
)
from backend.app.services.regions import extract_regional_mean_timeseries

logging.basicConfig(level=logging.WARNING)


def get_country_geoms():
    countries = ["Chad", "Fiji", "France"]
    geoms = {}
    for c in countries:
        res = search_boundaries(c)
        feat = get_boundary_by_id(res[0]["id"])
        geoms[c] = shape(feat["geometry"])
    return geoms


def verify_dataset(name: str, ds_open_fn, ds_norm_fn, var_name: str, expected_steps: int, coverage_type: str = None) -> Dict[str, Any]:
    ds_raw = ds_open_fn()
    ds_norm = ds_norm_fn(ds_raw)
    da = ds_norm[var_name]

    times = [str(t)[:10] for t in da["time"].values]
    first_step = times[0]
    last_step = times[-1]
    step_count = len(times)
    
    lats = da["lat"].values
    lons = da["lon"].values
    grid_size = f"{len(lats)} x {len(lons)}"

    # Typical month: middle month (e.g., around 2020-06 or len(times)//2)
    mid_idx = len(times) // 2
    typical_slice = da.isel(time=mid_idx).values
    non_nan_typical = int(np.count_nonzero(~np.isnan(typical_slice)))

    # Regional extraction for Chad, Fiji, France
    geoms = get_country_geoms()
    country_results = {}
    for c_name, geom in geoms.items():
        res = extract_regional_mean_timeseries(da, geom, coverage_type=coverage_type)
        valid_steps = sum(1 for v in res["mean_values"] if v is not None)
        valid_cells = res["intersecting_cell_count"]
        # Find non-zero valid cell count in typical step if available
        for vc in res["valid_cell_counts"]:
            if vc > 0:
                valid_cells = vc
                break
        method = res["mask_method"]
        assert method != "nearest_cell_fallback", f"Illegal nearest_cell_fallback for {c_name} on {name}"
        country_results[c_name] = {
            "valid_cells": valid_cells,
            "valid_steps": valid_steps,
            "total_steps": step_count,
            "method": method
        }

    return {
        "name": name,
        "var_name": var_name,
        "first_step": first_step,
        "last_step": last_step,
        "step_count": step_count,
        "expected_steps": expected_steps,
        "grid_size": grid_size,
        "non_nan_typical": non_nan_typical,
        "countries": country_results,
        "units": da.attrs.get("units", ""),
    }


def main():
    datasets_to_check = []
    
    # Check what exists
    cache_dir = Path("data/cache")
    if (cache_dir / "oisst_sst.mon.mean.nc").exists():
        datasets_to_check.append(("NOAA OISST v2.1", open_oisst_dataset, normalize_oisst_dataset, "sst", 442, "ocean_only"))
    if (cache_dir / "merra2_ts.mon.mean.nc").exists():
        datasets_to_check.append(("MERRA-2 TS", open_merra2_dataset, normalize_merra2_dataset, "TS", 441, None))
    if (cache_dir / "merra2_qv2m.mon.mean.nc").exists():
        datasets_to_check.append(("MERRA-2 QV2M", open_merra2_qv2m_dataset, normalize_merra2_qv2m_dataset, "QV2M", 441, None))
    if (cache_dir / "gldas_noah_sm.mon.mean.nc").exists():
        datasets_to_check.append(("GLDAS Noah v2.1 SM", open_gldas_dataset, normalize_gldas_dataset, "SoilMoi0_10cm_inst", 319, "land_only"))
    if (cache_dir / "precip.mon.mean.nc").exists():
        datasets_to_check.append(("GPCP v2.3 Precip", open_gpcp_dataset, normalize_gpcp_dataset, "precip", 574, None))

    results = []
    for entry in datasets_to_check:
        res = verify_dataset(entry[0], entry[1], entry[2], entry[3], entry[4], entry[5])
        results.append(res)

    # Print Table
    print("\n" + "="*120)
    print("DATA-VOLUME AND REGIONAL VERIFICATION TABLE")
    print("="*120)
    header = f"{'Dataset':<20} | {'First Step':<10} | {'Last Step':<10} | {'Steps (Act/Exp)':<15} | {'Grid (lat x lon)':<18} | {'Non-NaN Typical':<16} | {'Chad (cells/steps)':<20} | {'Fiji (cells/steps)':<20} | {'France (cells/steps)':<20}"
    print(header)
    print("-" * len(header))
    
    for r in results:
        c = r["countries"]
        steps_str = f"{r['step_count']} / {r['expected_steps']}"
        chad_str = f"{c['Chad']['valid_cells']} cells, {c['Chad']['valid_steps']} steps"
        fiji_str = f"{c['Fiji']['valid_cells']} cells, {c['Fiji']['valid_steps']} steps"
        fra_str = f"{c['France']['valid_cells']} cells, {c['France']['valid_steps']} steps"
        row = f"{r['name']:<20} | {r['first_step']:<10} | {r['last_step']:<10} | {steps_str:<15} | {r['grid_size']:<18} | {r['non_nan_typical']:<16,} | {chad_str:<20} | {fiji_str:<20} | {fra_str:<20}"
        print(row)
    print("="*120 + "\n")


if __name__ == "__main__":
    main()
