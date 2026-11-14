"""
GPCP V2.3 Data-Access Spike (Phase 0)

Discovers the NOAA PSL GPCP V2.3 monthly precipitation NetCDF file URL from:
https://www.psl.noaa.gov/data/gridded/data.gpcp.html
Opens the dataset with xarray via OPeNDAP or local cached download.
Inspects and prints dimensions, variable name, units, first/last time steps,
and missing-value conventions.
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path
import cftime
import numpy as np
import xarray as xr

PAGE_URL = "https://www.psl.noaa.gov/data/gridded/data.gpcp.html"
BASE_URL = "https://www.psl.noaa.gov"
DATA_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache"


def discover_gpcp_urls():
    """
    Scrapes the NOAA PSL GPCP webpage and queries the metadata database API
    to programmatically determine the exact NetCDF catalog, OPeNDAP, and download URLs.
    """
    print(f"[1/4] Discovering dataset metadata from {PAGE_URL}...")
    req = urllib.request.Request(PAGE_URL, headers={"User-Agent": "EarthScienceExplorer/0.1"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8")

    # Extract datasetID variable from page script
    match = re.search(r"var\s+datasetID\s*=\s*(\d+);", html)
    if not match:
        raise RuntimeError("Failed to locate datasetID in NOAA PSL GPCP HTML page.")
    dataset_id = match.group(1)
    print(f"      Found datasetID: {dataset_id}")

    # Query variables for this dataset
    var_api = f"{BASE_URL}/cgi-bin/mddb2/mddb2.py?action=getVariables&datasetID={dataset_id}"
    req_var = urllib.request.Request(var_api, headers={"User-Agent": "EarthScienceExplorer/0.1"})
    with urllib.request.urlopen(req_var, timeout=15) as resp:
        variables = json.loads(resp.read().decode("utf-8"))

    # Look for Monthly Mean Precipitation
    target_var = None
    for v in variables:
        # Looking for Precipitation ("Precipitation"), Mean ("Mean"), monthly timescale
        if v.get("v") == "Precipitation" and v.get("s") == "Mean":
            target_var = v
            break

    if not target_var:
        raise RuntimeError(f"Could not find Precipitation Mean variable in dataset {dataset_id}")

    var_id = target_var["i"]
    filepath = target_var["fp"]  # e.g., /Datasets/gpcp
    print(f"      Selected variable: {target_var['v']} (id: {var_id}, path: {filepath})")

    # Query files for this variable
    files_api = f"{BASE_URL}/cgi-bin/mddb2/mddb2.py?action=getVariableFiles&variableID={var_id}"
    req_files = urllib.request.Request(files_api, headers={"User-Agent": "EarthScienceExplorer/0.1"})
    with urllib.request.urlopen(req_files, timeout=15) as resp:
        files = json.loads(resp.read().decode("utf-8"))

    if not files:
        raise RuntimeError(f"No files returned for variableID {var_id}")

    filename = files[0]["filename"]  # e.g., precip.mon.mean.nc
    rel_path = f"{filepath.strip('/')}/{filename}"

    opendap_url = f"{BASE_URL}/thredds/dodsC/{rel_path}"
    download_url = f"https://downloads.psl.noaa.gov/{rel_path}"
    catalog_url = f"{BASE_URL}/thredds/catalog/{filepath.strip('/')}/catalog.html?dataset={rel_path}"

    print(f"      Discovered file: {filename}")
    print(f"      Catalog URL: {catalog_url}")
    print(f"      OPeNDAP URL: {opendap_url}")
    print(f"      Download URL: {download_url}")

    return {
        "dataset_id": dataset_id,
        "filename": filename,
        "opendap_url": opendap_url,
        "download_url": download_url,
        "catalog_url": catalog_url,
    }


def open_gpcp_dataset(urls: dict) -> xr.Dataset:
    """
    Attempts to open via OPeNDAP first. Falls back to downloading into data/cache.
    Note on NOAA PSL NetCDF convention:
    Opening with decode_times=False is required because 'time_bnds' in NOAA PSL GPCP V2.3
    contains an unmasked fill value (9.96921e+36) and a malformed time units string
    ('days since 1800-01-01 00:00:00 0:00') that causes standard CF datetime parsers
    to raise OutOfBoundsTimedelta.
    """
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    local_path = DATA_CACHE_DIR / urls["filename"]

    # Try OPeNDAP first
    print(f"[2/4] Opening dataset via OPeNDAP: {urls['opendap_url']}...")
    try:
        ds = xr.open_dataset(urls["opendap_url"], decode_times=False)
        print("      Successfully connected and opened remote OPeNDAP dataset.")
        return ds
    except Exception as opendap_err:
        print(f"      OPeNDAP connection failed ({opendap_err}). Falling back to cached download...")

    # Download fallback
    if not local_path.exists():
        print(f"      Downloading {urls['download_url']} to {local_path}...")
        req = urllib.request.Request(urls["download_url"], headers={"User-Agent": "EarthScienceExplorer/0.1"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(local_path, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        print(f"      Downloaded {local_path.stat().st_size} bytes.")
    else:
        print(f"      Found existing cached file at {local_path}.")

    ds = xr.open_dataset(local_path, decode_times=False)
    return ds


def inspect_gpcp(ds: xr.Dataset):
    """
    Extracts and prints required metadata:
    - Dimensions
    - Variable name
    - Units
    - First and last time steps
    - Missing-value convention
    """
    print("[3/4] Inspecting GPCP V2.3 dataset metadata...")

    # 1. Dimensions
    dims = dict(ds.sizes)
    print(f"\n================ GPCP V2.3 METADATA ================")
    print(f"Dimensions: {dims}")
    for dim_name, size in dims.items():
        print(f"  - {dim_name}: {size}")

    # 2. Variable name
    var_name = "precip"
    if var_name not in ds.data_vars:
        raise KeyError(f"Variable '{var_name}' not found in dataset. Variables: {list(ds.data_vars)}")
    precip_var = ds[var_name]
    print(f"\nPrimary Variable Name: '{var_name}'")
    print(f"  Long Name: {precip_var.attrs.get('long_name')}")
    print(f"  Standard/Var Desc: {precip_var.attrs.get('var_desc')}")

    # 3. Units
    units = precip_var.attrs.get("units")
    print(f"\nUnits: {units}")

    # 4. First and last time step
    time_raw = ds["time"].values
    time_units = ds["time"].attrs.get("units")
    time_calendar = ds["time"].attrs.get("calendar", "standard")
    decoded_dates = cftime.num2date(time_raw, time_units, calendar=time_calendar)

    first_time = decoded_dates[0]
    last_time = decoded_dates[-1]
    print(f"\nTime Coordinate Coverage:")
    print(f"  Raw Units: {time_units}")
    print(f"  Total Steps: {len(decoded_dates)}")
    print(f"  First Time Step: {first_time.strftime('%Y-%m-%d')}")
    print(f"  Last Time Step:  {last_time.strftime('%Y-%m-%d')}")

    # 5. Missing-value convention
    missing_val_attr = precip_var.attrs.get("missing_value")
    fill_val_attr = precip_var.attrs.get("_FillValue")
    encoding_missing = precip_var.encoding.get("missing_value")
    encoding_fill = precip_var.encoding.get("_FillValue")
    valid_range = precip_var.attrs.get("valid_range")
    actual_range = precip_var.attrs.get("actual_range")

    print(f"\nMissing-Value Convention:")
    print(f"  Attribute missing_value: {missing_val_attr}")
    print(f"  Attribute _FillValue:    {fill_val_attr}")
    print(f"  Encoding missing_value:  {encoding_missing}")
    print(f"  Encoding _FillValue:     {encoding_fill}")
    print(f"  Valid Range:             {valid_range}")
    print(f"  Actual Range:            {actual_range}")
    print(f"  Missing Value Constant:  -9.96921e+36 (or NC_FILL_FLOAT)")
    print(f"  Handling Policy:         Decode fill/missing values to NaN (Rule 3: Missing is never zero).")
    print(f"====================================================\n")

    return {
        "dimensions": dims,
        "variable_name": var_name,
        "units": units,
        "first_time": first_time.strftime("%Y-%m-%d"),
        "last_time": last_time.strftime("%Y-%m-%d"),
        "missing_value": float(encoding_missing) if encoding_missing is not None else -9.96921e36,
        "valid_range": [float(v) for v in valid_range] if valid_range is not None else None,
        "actual_range": [float(v) for v in actual_range] if actual_range is not None else None,
    }


def main():
    try:
        urls = discover_gpcp_urls()
        ds = open_gpcp_dataset(urls)
        summary = inspect_gpcp(ds)
        ds.close()
        print("[4/4] GPCP Spike completed successfully.")
        return 0
    except Exception as e:
        print(f"ERROR running GPCP spike: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
