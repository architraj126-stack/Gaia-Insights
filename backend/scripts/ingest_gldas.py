"""
GLDAS Noah 0.25 Degree Monthly v2.1 Real Ingestion Script (SPEC 6.3, 14.1, 15.1, 15.2).

Collection: C1342986036-GES_DISC (GLDAS_NOAH025_M.2.1)
Field: SoilMoi0_10cm_inst (Soil moisture 0-10 cm)
Time range: 2000-01 to 2026-10 (322 monthly steps)
OPeNDAP Subsetting URL: opendap.earthdata.nasa.gov
"""
import concurrent.futures
import hashlib
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx
import requests
import xarray as xr
import cftime
import numpy as np

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from backend.app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_gldas")

DATA_CACHE_DIR = Path("data/cache")
DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR = DATA_CACHE_DIR / "tmp_gldas"
TMP_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FILE = DATA_CACHE_DIR / "gldas_noah_sm.mon.mean.nc"
MANIFEST_FILE = DATA_CACHE_DIR / "gldas_manifest.json"

COLLECTION_ID = "C1342986036-GES_DISC"
START_DATE = "2000-01-01T00:00:00Z"
END_DATE = "2026-10-31T23:59:59Z"


def get_all_gldas_granules(token: str) -> list[dict]:
    """Queries NASA CMR for all GLDAS_NOAH025_M.2.1 granules between 2000-01 and 2026-10."""
    logger.info("Querying NASA CMR for collection %s granules between %s and %s...", COLLECTION_ID, START_DATE, END_DATE)
    headers = {"Authorization": f"Bearer {token}"}
    granules = []
    page = 1
    page_size = 200

    while True:
        url = f"https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id={COLLECTION_ID}&temporal={START_DATE},{END_DATE}&page_size={page_size}&page_num={page}&sort_key=start_date"
        resp = httpx.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        entries = resp.json().get("feed", {}).get("entry", [])
        if not entries:
            break
        granules.extend(entries)
        logger.info("Fetched page %d (%d granules total so far)", page, len(granules))
        if len(entries) < page_size:
            break
        page += 1

    logger.info("Found %d granules in NASA CMR for requested period.", len(granules))
    return granules


def download_single_granule(entry: dict, token: str) -> tuple[str, Path]:
    title = entry["title"]
    # Title format: GLDAS_NOAH025_M.2.1:GLDAS_NOAH025_M.A200001.021.nc4
    granule_id = title.split(":")[-1] if ":" in title else title
    # Date part from AYYYYMM, e.g. GLDAS_NOAH025_M.A200001.021.nc4 -> 200001
    parts = granule_id.split(".")
    # part with A200001
    date_part = [p for p in parts if p.startswith("A") and len(p) == 7][0][1:]
    
    tmp_path = TMP_DIR / f"{granule_id}.nc4"
    if tmp_path.exists() and tmp_path.stat().st_size > 100_000:
        return date_part, tmp_path

    # Construct OPeNDAP subset URL
    encoded_id = f"GLDAS_NOAH025_M.2.1%3A{granule_id}"
    opendap_url = f"https://opendap.earthdata.nasa.gov/collections/{COLLECTION_ID}/granules/{encoded_id}.nc4?SoilMoi0_10cm_inst,time,lat,lon"

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})

    tmp_part = tmp_path.with_suffix(".tmp")
    for attempt in range(5):
        try:
            r = session.get(opendap_url, timeout=30)
            if r.status_code == 200:
                tmp_part.write_bytes(r.content)
                tmp_part.replace(tmp_path)
                return date_part, tmp_path
            elif r.status_code == 404:
                # Try raw granule URL if opendap encoded differently
                links = [l["href"] for l in entry.get("links", []) if "opendap" in l.get("href", "")]
                if links:
                    r2 = session.get(f"{links[0]}.nc4?SoilMoi0_10cm_inst,time,lat,lon", timeout=30)
                    if r2.status_code == 200:
                        tmp_part.write_bytes(r2.content)
                        tmp_part.replace(tmp_path)
                        return date_part, tmp_path
            logger.warning("Attempt %d for %s returned status %d", attempt, granule_id, r.status_code)
        except Exception as e:
            logger.warning("Attempt %d for %s failed: %s", attempt, granule_id, e)
        finally:
            if tmp_part.exists():
                tmp_part.unlink(missing_ok=True)
        time.sleep(2 * (attempt + 1))

    raise RuntimeError(f"Failed to download OPeNDAP subset for granule {granule_id}")


def main():
    token = settings.EARTHDATA_TOKEN
    if not token:
        logger.error("EARTHDATA_TOKEN missing from settings!")
        sys.exit(1)

    logger.info("Starting real ingestion for NASA GLDAS Noah v2.1 Soil Moisture...")
    granules = get_all_gldas_granules(token)
    num_granules = len(granules)
    logger.info("Found %d granules in NASA CMR (latest complete month: %s)", num_granules, granules[-1]["title"])

    logger.info("Downloading %d granule subsets via OPeNDAP with 12 parallel workers...", num_granules)
    granule_files: dict[str, Path] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futures = {ex.submit(download_single_granule, g, token): g for g in granules}
        done = 0
        for f in concurrent.futures.as_completed(futures):
            date_part, p = f.result()
            granule_files[date_part] = p
            done += 1
            if done % 20 == 0 or done == len(granules):
                logger.info("Downloaded %d / %d granules (%.1f%%)", done, len(granules), done * 100.0 / len(granules))

    sorted_dates = sorted(granule_files.keys())
    first_date_str = f"{sorted_dates[0][:4]}-{sorted_dates[0][4:6]}-01"
    last_date_str = f"{sorted_dates[-1][:4]}-{sorted_dates[-1][4:6]}-01"
    logger.info("Sorting and concatenating %d monthly datasets (%s to %s)...", len(sorted_dates), first_date_str, last_date_str)

    datasets = []
    for d in sorted_dates:
        ds_m = xr.open_dataset(granule_files[d], decode_times=False, engine="netcdf4")
        datasets.append(ds_m)

    ds_full = xr.concat(datasets, dim="time")
    import cftime
    from datetime import datetime

    time_units = "days since 2000-01-01 00:00:00"
    time_objs = [datetime(int(d[:4]), int(d[4:6]), 1) for d in sorted_dates]
    time_nums = cftime.date2num(time_objs, units=time_units, calendar="standard")
    ds_full = ds_full.assign_coords(time=time_nums)
    ds_full["time"].attrs = {
        "long_name": "time",
        "units": time_units,
        "calendar": "standard",
        "axis": "T",
    }

    logger.info("Combined dataset dimensions: %s", dict(ds_full.sizes))
    assert ds_full.sizes["time"] == num_granules, f"Expected {num_granules} time steps, got {ds_full.sizes['time']}"
    assert ds_full.sizes["lat"] == 600, f"Expected 600 lats, got {ds_full.sizes['lat']}"
    assert ds_full.sizes["lon"] == 1440, f"Expected 1440 lons, got {ds_full.sizes['lon']}"
    assert "SoilMoi0_10cm_inst" in ds_full.data_vars, "SoilMoi0_10cm_inst missing!"

    # Save safely to target file
    logger.info("Saving GLDAS Noah Soil Moisture to %s...", TARGET_FILE)
    temp_target = TARGET_FILE.with_suffix(".nc.saving")
    encoding = {"SoilMoi0_10cm_inst": {"zlib": True, "complevel": 4, "shuffle": True, "_FillValue": -9999.0}}
    ds_full.to_netcdf(temp_target, encoding=encoding)
    temp_target.replace(TARGET_FILE)
    logger.info("Target file saved: %s (%d bytes)", TARGET_FILE, TARGET_FILE.stat().st_size)

    # Clean up tmp directory
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    logger.info("Cleaned up tmp directory %s", TMP_DIR)

    # Compute checksum
    hasher = hashlib.sha256()
    with open(TARGET_FILE, "rb") as f:
        while c := f.read(8 * 1024 * 1024):
            hasher.update(c)
    sha256_hash = hasher.hexdigest()
    logger.info("Computed SHA-256: %s", sha256_hash)

    # Write Manifest
    manifest = {
        "dataset_id": "gldas_noah_sm",
        "product_name": "GLDAS Noah Land Surface Model L4 monthly 0.25 x 0.25 degree V2.1",
        "provider": "NASA GES DISC",
        "collection_id": COLLECTION_ID,
        "version": "v2.1",
        "source_url": f"https://opendap.earthdata.nasa.gov/collections/{COLLECTION_ID}/",
        "sha256": sha256_hash,
        "retrieval_date": datetime.now(timezone.utc).isoformat(),
        "time_range": [first_date_str, last_date_str],
        "time_steps": num_granules,
        "spatial_grid": "regular_lat_lon",
        "cell_dimensions": [0.25, 0.25],
        "grid_shape": [600, 1440],
        "native_units": "kg m-2",
        "fill_value": -9999.0,
        "subset_method": "OPeNDAP single-variable extraction"
    }
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))
    logger.info("Manifest written to %s", MANIFEST_FILE)
    print("SUCCESS_GLDAS_INGESTION_COMPLETED")


if __name__ == "__main__":
    main()
