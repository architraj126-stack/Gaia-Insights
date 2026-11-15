"""
MERRA-2 TS and QV2M Real Ingestion Script (SPEC 6.1, 14.1, 15.1, 15.2).

Collection: C1276812859-GES_DISC (M2TMNXSLV.5.12.4)
Fields: TS (Surface skin temperature) and QV2M (2-meter specific humidity)
Time range: 1990-01 to 2026-10 (442 monthly steps)
OPeNDAP Subsetting URL: opendap.earthdata.nasa.gov
"""
import concurrent.futures
import hashlib
import json
import logging
import os
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
logger = logging.getLogger("ingest_merra2")

DATA_CACHE_DIR = Path("data/cache")
DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR = DATA_CACHE_DIR / "tmp_merra2"
TMP_DIR.mkdir(parents=True, exist_ok=True)

TARGET_TS_FILE = DATA_CACHE_DIR / "merra2_ts.mon.mean.nc"
TARGET_QV2M_FILE = DATA_CACHE_DIR / "merra2_qv2m.mon.mean.nc"
MANIFEST_TS_FILE = DATA_CACHE_DIR / "merra2_ts_manifest.json"
MANIFEST_QV2M_FILE = DATA_CACHE_DIR / "merra2_qv2m_manifest.json"

COLLECTION_ID = "C1276812859-GES_DISC"
START_DATE = "1990-01-01T00:00:00Z"
END_DATE = "2026-10-31T23:59:59Z"


def get_all_merra2_granules(token: str) -> list[dict]:
    """Queries NASA CMR for all M2TMNXSLV granules between 1990-01 and 2026-10."""
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
    # Extract date from title: e.g. MERRA2_100.tavgM_2d_slv_Nx.199001.nc4
    # Granule date YYYYMM
    granule_id = title.split(":")[-1] if ":" in title else title
    parts = granule_id.split(".")
    date_part = parts[-2]  # e.g. 199001
    
    # Target tmp file
    tmp_path = TMP_DIR / f"{granule_id}.nc4"
    if tmp_path.exists() and tmp_path.stat().st_size > 100_000:
        return date_part, tmp_path

    # Construct OPeNDAP subset URL
    # https://opendap.earthdata.nasa.gov/collections/C1276812859-GES_DISC/granules/M2TMNXSLV.5.12.4%3A{granule_id}.nc4?TS,QV2M,time,lat,lon
    encoded_id = f"M2TMNXSLV.5.12.4%3A{granule_id}"
    opendap_url = f"https://opendap.earthdata.nasa.gov/collections/{COLLECTION_ID}/granules/{encoded_id}.nc4?TS,QV2M,time,lat,lon"

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
                    r2 = session.get(f"{links[0]}.nc4?TS,QV2M,time,lat,lon", timeout=30)
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

    logger.info("Starting real ingestion for MERRA-2 TS and QV2M...")
    granules = get_all_merra2_granules(token)
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

    time_units = "days since 1980-01-01 00:00:00"
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
    assert ds_full.sizes["lat"] == 361, f"Expected 361 lats, got {ds_full.sizes['lat']}"
    assert ds_full.sizes["lon"] == 576, f"Expected 576 lons, got {ds_full.sizes['lon']}"
    assert "TS" in ds_full.data_vars, "TS missing!"
    assert "QV2M" in ds_full.data_vars, "QV2M missing!"

    # 1. Save TS dataset safely
    logger.info("Saving MERRA-2 TS to %s...", TARGET_TS_FILE)
    ds_ts = ds_full[["TS", "lat", "lon", "time"]]
    temp_ts = TARGET_TS_FILE.with_suffix(".nc.saving")
    encoding_ts = {"TS": {"zlib": True, "complevel": 4, "shuffle": True, "_FillValue": 1.0e15}}
    ds_ts.to_netcdf(temp_ts, encoding=encoding_ts)
    temp_ts.replace(TARGET_TS_FILE)

    # 2. Save QV2M dataset safely
    logger.info("Saving MERRA-2 QV2M to %s...", TARGET_QV2M_FILE)
    ds_qv2m = ds_full[["QV2M", "lat", "lon", "time"]]
    temp_qv2m = TARGET_QV2M_FILE.with_suffix(".nc.saving")
    encoding_qv2m = {"QV2M": {"zlib": True, "complevel": 4, "shuffle": True, "_FillValue": 1.0e15}}
    ds_qv2m.to_netcdf(temp_qv2m, encoding=encoding_qv2m)
    temp_qv2m.replace(TARGET_QV2M_FILE)

    # Clean up tmp directory
    import shutil
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    logger.info("Cleaned up tmp directory %s", TMP_DIR)

    # Compute checksums
    def get_sha256(p: Path) -> str:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while c := f.read(8 * 1024 * 1024):
                h.update(c)
        return h.hexdigest()

    ts_hash = get_sha256(TARGET_TS_FILE)
    qv2m_hash = get_sha256(TARGET_QV2M_FILE)

    # Manifests
    now_iso = datetime.now(timezone.utc).isoformat()
    manifest_ts = {
        "dataset_id": "merra2_monthly_ts",
        "product_name": "MERRA-2 tavgM_2d_slv_Nx: 2d,Monthly mean,Time-Averaged,Single-Level,Assimilation,Single-Level Diagnostics 0.625 x 0.5 degree V5.12.4",
        "provider": "NASA GES DISC / GMAO",
        "collection_id": COLLECTION_ID,
        "version": "5.12.4",
        "source_url": f"https://opendap.earthdata.nasa.gov/collections/{COLLECTION_ID}/",
        "sha256": ts_hash,
        "retrieval_date": now_iso,
        "time_range": [first_date_str, last_date_str],
        "time_steps": num_granules,
        "spatial_grid": "regular_lat_lon",
        "cell_dimensions": [0.625, 0.5],
        "grid_shape": [361, 576],
        "native_units": "K",
        "fill_value": 1.0e15,
        "subset_method": "OPeNDAP single-variable extraction"
    }
    MANIFEST_TS_FILE.write_text(json.dumps(manifest_ts, indent=2))

    manifest_qv2m = {
        "dataset_id": "merra2_monthly_qv2m",
        "product_name": "MERRA-2 tavgM_2d_slv_Nx: 2d,Monthly mean,Time-Averaged,Single-Level,Assimilation,Single-Level Diagnostics 0.625 x 0.5 degree V5.12.4",
        "provider": "NASA GES DISC / GMAO",
        "collection_id": COLLECTION_ID,
        "version": "5.12.4",
        "source_url": f"https://opendap.earthdata.nasa.gov/collections/{COLLECTION_ID}/",
        "sha256": qv2m_hash,
        "retrieval_date": now_iso,
        "time_range": [first_date_str, last_date_str],
        "time_steps": num_granules,
        "spatial_grid": "regular_lat_lon",
        "cell_dimensions": [0.625, 0.5],
        "grid_shape": [361, 576],
        "native_units": "kg kg-1",
        "fill_value": 1.0e15,
        "subset_method": "OPeNDAP single-variable extraction"
    }
    MANIFEST_QV2M_FILE.write_text(json.dumps(manifest_qv2m, indent=2))

    logger.info("MERRA-2 TS and QV2M ingestion complete.")
    print("SUCCESS_MERRA2_INGESTION_COMPLETED")


if __name__ == "__main__":
    main()
