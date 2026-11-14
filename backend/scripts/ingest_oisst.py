"""
NOAA OISST v2.1 Real Data Ingestion Script.

Source: NOAA Physical Sciences Laboratory (PSL)
Page: https://www.psl.noaa.gov/data/gridded/data.noaa.oisst.v2.highres.html
Exact URL: https://downloads.psl.noaa.gov/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc
"""
import concurrent.futures
import hashlib
import json
import logging
import os
import socket
import sys
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
import cftime
import numpy as np
import xarray as xr

socket.setdefaulttimeout(35)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_oisst")

DATA_CACHE_DIR = Path("data/cache")
DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_URL = "https://downloads.psl.noaa.gov/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc"
PART_FILE = DATA_CACHE_DIR / "oisst_download.tmp"
STATE_FILE = DATA_CACHE_DIR / "oisst_chunks.json"
TARGET_FILE = DATA_CACHE_DIR / "oisst_sst.mon.mean.nc"
MANIFEST_FILE = DATA_CACHE_DIR / "oisst_manifest.json"

CHUNK_SIZE = 20 * 1024 * 1024  # 20 MB
TOTAL_SIZE = 2247856453
NUM_CHUNKS = (TOTAL_SIZE + CHUNK_SIZE - 1) // CHUNK_SIZE  # 113 chunks
MAX_WORKERS = 2


def fetch_chunk(chunk_idx: int) -> int:
    start = chunk_idx * CHUNK_SIZE
    end = min(start + CHUNK_SIZE - 1, TOTAL_SIZE - 1)
    headers = {"Range": f"bytes={start}-{end}", "User-Agent": "EarthScienceExplorer/1.0"}
    expected = end - start + 1
    
    for attempt in range(8):
        try:
            resp = requests.get(SOURCE_URL, headers=headers, timeout=(15, 180))
            if resp.status_code not in (200, 206):
                raise IOError(f"HTTP status {resp.status_code}")
            data = resp.content
            if len(data) != expected:
                raise IOError(f"Incomplete chunk {chunk_idx}: got {len(data)}, expected {expected}")
            with open(PART_FILE, "r+b") as f:
                f.seek(start)
                f.write(data)
            return chunk_idx
        except Exception as e:
            time.sleep(3 * (attempt + 1))
            if attempt == 7:
                raise RuntimeError(f"Chunk {chunk_idx} failed after 8 retries: {e}")


def main():
    logger.info("Starting NOAA OISST v2.1 real ingestion from %s", SOURCE_URL)
    logger.info("Total size: %d bytes, Chunks: %d x 20MB, Workers: %d", TOTAL_SIZE, NUM_CHUNKS, MAX_WORKERS)

    if not PART_FILE.exists() or PART_FILE.stat().st_size != TOTAL_SIZE:
        logger.info("Allocating %s (%d bytes)...", PART_FILE, TOTAL_SIZE)
        with open(PART_FILE, "wb") as f:
            f.seek(TOTAL_SIZE - 1)
            f.write(b"\0")
        completed = set()
    else:
        if STATE_FILE.exists():
            try:
                completed = set(json.loads(STATE_FILE.read_text()))
                logger.info("Resuming: %d / %d chunks already downloaded", len(completed), NUM_CHUNKS)
            except Exception:
                completed = set()
        else:
            completed = set()

    remaining = [i for i in range(NUM_CHUNKS) if i not in completed]
    logger.info("Remaining chunks to download: %d", len(remaining))

    t0 = time.time()
    last_log = time.time()

    if remaining:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_chunk, idx): idx for idx in remaining}
            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]
                future.result()
                completed.add(idx)
                if time.time() - last_log > 5 or len(completed) == NUM_CHUNKS:
                    STATE_FILE.write_text(json.dumps(sorted(list(completed))))
                    last_log = time.time()
                    elapsed = time.time() - t0
                    mb_done = len(completed) * 20
                    pct = len(completed) * 100.0 / NUM_CHUNKS
                    logger.info("OISST Progress: %d/%d chunks (%.1f%%, ~%d MB) in %.1fs", len(completed), NUM_CHUNKS, pct, mb_done, elapsed)

    logger.info("All %d chunks complete. Verifying SHA-256...", NUM_CHUNKS)
    hasher = hashlib.sha256()
    with open(PART_FILE, "rb") as f:
        while chunk := f.read(16 * 1024 * 1024):
            hasher.update(chunk)
    sha256_hash = hasher.hexdigest()
    logger.info("Computed SHA-256: %s", sha256_hash)

    # Slice 1990-01 to 2026-10
    logger.info("Opening downloaded raw NetCDF with xarray...")
    ds = xr.open_dataset(PART_FILE, decode_times=False)
    
    time_units = ds["time"].attrs.get("units", "days since 1800-01-01 00:00:00")
    calendar = ds["time"].attrs.get("calendar", "gregorian")
    raw_times = ds["time"].values
    dates = cftime.num2date(raw_times, units=time_units, calendar=calendar)
    date_strs = [f"{d.year:04d}-{d.month:02d}-01" for d in dates]

    indices = [i for i, d in enumerate(date_strs) if "1990-01-01" <= d <= "2026-10-01"]
    logger.info("Selecting time steps: %d steps (from %s to %s)", len(indices), date_strs[indices[0]], date_strs[indices[-1]])
    assert len(indices) == 442, f"Expected 442 steps, got {len(indices)}"

    ds_sub = ds.isel(time=indices)
    
    # Save safely to target file
    temp_target = TARGET_FILE.with_suffix(".nc.tmp")
    logger.info("Writing sliced dataset to %s...", temp_target)
    encoding = {
        "sst": {"zlib": True, "complevel": 4, "shuffle": True, "_FillValue": -9.96921e36}
    }
    ds_sub.to_netcdf(temp_target, encoding=encoding)
    ds.close()
    ds_sub.close()

    temp_target.replace(TARGET_FILE)
    logger.info("Target file saved: %s (%d bytes)", TARGET_FILE, TARGET_FILE.stat().st_size)

    # Clean up temporary files per rule: Never leave a .part file in data/cache
    PART_FILE.unlink(missing_ok=True)
    STATE_FILE.unlink(missing_ok=True)
    logger.info("Cleaned up temporary download files.")

    # Write Manifest
    manifest = {
        "dataset_id": "noaa_oisst_v21",
        "product_name": "NOAA 1/4° Daily Optimum Interpolation Sea Surface Temperature (OISST) Version 2.1",
        "provider": "NOAA NCEI / PSL",
        "version": "v2.1",
        "source_url": SOURCE_URL,
        "sha256": sha256_hash,
        "retrieval_date": datetime.now(timezone.utc).isoformat(),
        "time_range": ["1990-01-01", "2026-10-01"],
        "time_steps": 442,
        "spatial_grid": "regular_lat_lon",
        "cell_dimensions": [0.25, 0.25],
        "grid_shape": [720, 1440],
        "native_units": "degC",
        "fill_value": -9.96921e36,
        "ocean_mask": "native_ocean_mask"
    }
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))
    logger.info("Manifest written to %s", MANIFEST_FILE)
    print("SUCCESS_OISST_INGESTION_COMPLETED")


if __name__ == "__main__":
    main()
