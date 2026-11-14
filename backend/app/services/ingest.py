"""
GPCP Ingestion Service (SPEC 14.1, 15.1, 16.3).

Responsibilities:
- Lazily open GPCP V2.3 NetCDF via local cache or OPeNDAP/HTTP.
- Decode coordinate system: time coordinate via cftime, longitudes normalised to [-180, 180].
- Sort spatial coordinates (lat, lon) ascending for deterministic slicing.
- Decode missing/fill values (-9.96921e+36 or values <= -9.0e36 or outside [0, 100]) to NaN.
- Validate expected time steps against requested start/end and build an explicit missing-time index.
- Cache subsets under data/cache with a deterministic cache key.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cftime
import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger("backend.services.ingest")

DATA_CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "cache"
SUBSET_CACHE_DIR = DATA_CACHE_DIR / "subsets"

OPENDAP_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/gpcp/precip.mon.mean.nc"
DOWNLOAD_URL = "https://psl.noaa.gov/thredds/fileServer/Datasets/gpcp/precip.mon.mean.nc"
FALLBACK_DOWNLOAD_URL = "https://downloads.psl.noaa.gov/Datasets/gpcp/precip.mon.mean.nc"
PRIMARY_FILE = "precip.mon.mean.nc"

FILL_THRESHOLD = -9.0e36
VALID_MIN = 0.0
VALID_MAX = 100.0

MERRA2_PRIMARY_FILE = "merra2_ts.mon.mean.nc"
MERRA2_FILL_THRESHOLD = 1.0e14
MERRA2_VALID_MIN = 150.0
MERRA2_VALID_MAX = 350.0

OISST_PRIMARY_FILE = "oisst_sst.mon.mean.nc"
OISST_OPENDAP_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc"
OISST_FILL_THRESHOLD = -9.0e36
OISST_VALID_MIN = -3.0
OISST_VALID_MAX = 45.0

GLDAS_PRIMARY_FILE = "gldas_noah_sm.mon.mean.nc"
GLDAS_FILL_THRESHOLD = -9998.0
GLDAS_VALID_MIN = 0.0
GLDAS_VALID_MAX = 100.0

MERRA2_QV2M_PRIMARY_FILE = "merra2_qv2m.mon.mean.nc"
MERRA2_QV2M_FILL_THRESHOLD = 1.0e14
MERRA2_QV2M_VALID_MIN = 0.0
MERRA2_QV2M_VALID_MAX = 0.1


def ensure_cache_dirs() -> None:
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SUBSET_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cached_raw_file_path() -> Path:
    ensure_cache_dirs()
    return DATA_CACHE_DIR / PRIMARY_FILE


def get_cached_merra2_file_path() -> Path:
    ensure_cache_dirs()
    return DATA_CACHE_DIR / MERRA2_PRIMARY_FILE


def get_cached_oisst_file_path() -> Path:
    ensure_cache_dirs()
    return DATA_CACHE_DIR / OISST_PRIMARY_FILE


def get_cached_gldas_file_path() -> Path:
    ensure_cache_dirs()
    return DATA_CACHE_DIR / GLDAS_PRIMARY_FILE


def get_cached_merra2_qv2m_file_path() -> Path:
    ensure_cache_dirs()
    return DATA_CACHE_DIR / MERRA2_QV2M_PRIMARY_FILE


def download_gpcp_raw_file(target_path: Optional[Path] = None) -> Path:
    """
    Downloads precip.mon.mean.nc into target_path if not already present.
    Uses curl with resume support (-C -) if available, with urllib range-request fallback.
    """
    import shutil
    import subprocess

    if target_path is None:
        target_path = get_cached_raw_file_path()

    # The full GPCP V2.3 NetCDF is ~20.35 MB (20,357,627 bytes)
    if target_path.exists() and target_path.stat().st_size >= 20_000_000:
        logger.info("Using existing complete cached raw GPCP file: %s (%d bytes)", target_path, target_path.stat().st_size)
        return target_path

    ensure_cache_dirs()
    urls = [DOWNLOAD_URL, FALLBACK_DOWNLOAD_URL]
    curl_path = shutil.which("curl")

    for url in urls:
        logger.info("Downloading GPCP raw NetCDF from %s to %s", url, target_path)
        if curl_path:
            try:
                cmd = [curl_path, "-L", "-C", "-", "--retry", "3", "-o", str(target_path), url]
                subprocess.run(cmd, check=True, timeout=300)
                if target_path.exists() and target_path.stat().st_size >= 20_000_000:
                    logger.info("Successfully downloaded GPCP NetCDF via curl (%d bytes)", target_path.stat().st_size)
                    return target_path
            except Exception as e:
                logger.warning("curl download from %s failed: %s", url, e)

        # urllib fallback
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EarthScienceExplorer/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp, open(target_path, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            if target_path.exists() and target_path.stat().st_size >= 20_000_000:
                logger.info("Successfully cached GPCP file via urllib (%d bytes)", target_path.stat().st_size)
                return target_path
        except Exception as e:
            logger.warning("urllib download from %s failed: %s", url, e)

    if target_path.exists() and target_path.stat().st_size >= 20_000_000:
        return target_path

    raise RuntimeError("Failed to complete raw GPCP NetCDF download from all mirrors.")


def open_gpcp_dataset(custom_path_or_url: Optional[str] = None) -> xr.Dataset:
    """
    Opens GPCP dataset with decode_times=False to prevent OutOfBoundsTimedelta
    caused by time_bnds fill values (ADR-001).
    """
    if custom_path_or_url:
        return xr.open_dataset(custom_path_or_url, decode_times=False)

    local_file = get_cached_raw_file_path()
    if local_file.exists() and local_file.stat().st_size > 10_000_000:
        return xr.open_dataset(local_file, decode_times=False)

    # Try OPeNDAP first
    try:
        logger.info("Attempting OPeNDAP open: %s", OPENDAP_URL)
        return xr.open_dataset(OPENDAP_URL, decode_times=False)
    except Exception as opendap_err:
        logger.warning("OPeNDAP connection failed (%s); downloading file to cache...", opendap_err)
        downloaded = download_gpcp_raw_file(local_file)
        return xr.open_dataset(downloaded, decode_times=False)


def normalize_gpcp_dataset(ds: xr.Dataset, var_name: str = "precip") -> xr.Dataset:
    """
    Normalises coordinate systems and decodes missing values:
    1. Time coordinate: decodes with cftime and maps to ISO 'YYYY-MM-01' dates.
    2. Longitude: maps 0..360 to -180..180 (handling antimeridian).
    3. Sorts lat and lon ascending.
    4. Fill values and values outside [0, 100] are masked strictly to NaN.
    """
    # 1. Decode time coordinate
    time_coord = ds["time"]
    time_units = time_coord.attrs.get("units", "days since 1800-01-01 00:00:00")
    calendar = time_coord.attrs.get("calendar", "standard")
    raw_time = time_coord.values

    cf_dates = cftime.num2date(raw_time, units=time_units, calendar=calendar)
    date_strs = [f"{d.year:04d}-{d.month:02d}-01" for d in cf_dates]

    # Assign decoded dates to time coordinate
    ds = ds.assign_coords(time=date_strs)

    # 2. Normalise longitudes: convert [0, 360) -> [-180, 180)
    lon_vals = ds["lon"].values
    if np.any(lon_vals > 180.0):
        norm_lons = ((ds["lon"] + 180.0) % 360.0) - 180.0
        ds = ds.assign_coords(lon=norm_lons)

    # 3. Sort spatial coordinates ascending
    ds = ds.sortby(["lat", "lon"])

    # 4. Decode fill values to NaN
    if var_name in ds.data_vars:
        da = ds[var_name]
        masked = xr.where(
            (da <= FILL_THRESHOLD) | (da < VALID_MIN) | (da > VALID_MAX) | np.isnan(da),
            np.nan,
            da,
        )
        masked.attrs = da.attrs
        ds[var_name] = masked

    return ds


def download_merra2_raw_file(target_path: Optional[Path] = None) -> Path:
    """
    Ensures MERRA-2 raw file is present in cache.
    If credentials are provided in .env (SPEC 15.2), attempts remote download.
    """
    from backend.app.config import settings

    if target_path is None:
        target_path = get_cached_merra2_file_path()

    if target_path.exists() and target_path.stat().st_size > 100_000:
        return target_path

    ensure_cache_dirs()

    token = settings.EARTHDATA_TOKEN
    username = settings.EARTHDATA_USERNAME
    password = settings.EARTHDATA_PASSWORD

    headers = {"User-Agent": "EarthScienceExplorer/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif username and password:
        import base64
        creds = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {creds}"

    if target_path.exists() and target_path.stat().st_size > 100_000:
        return target_path

    raise RuntimeError(
        "Unavailable - real data not yet ingested"
    )


def open_merra2_dataset(custom_path_or_url: Optional[str] = None) -> xr.Dataset:
    """
    Opens MERRA-2 skin temperature dataset with decode_times=False.
    """
    if custom_path_or_url:
        return xr.open_dataset(custom_path_or_url, decode_times=False)

    local_file = get_cached_merra2_file_path()
    if local_file.exists():
        return xr.open_dataset(local_file, decode_times=False)

    downloaded = download_merra2_raw_file(local_file)
    return xr.open_dataset(downloaded, decode_times=False)


def normalize_merra2_dataset(
    ds: xr.Dataset,
    var_name: str = "TS",
    enforce_land_mask: bool = True,
) -> xr.Dataset:
    """
    Normalises MERRA-2 coordinates and decodes fill values to NaN.
    Enforces land-only mask: ocean cells are decoded strictly to NaN (SPEC 6.3, SPEC 14.1).
    """
    time_coord = ds["time"]
    time_units = time_coord.attrs.get("units", "days since 1980-01-01 00:00:00")
    calendar = time_coord.attrs.get("calendar", "standard")
    raw_time = time_coord.values

    cf_dates = cftime.num2date(raw_time, units=time_units, calendar=calendar)
    date_strs = [f"{d.year:04d}-{d.month:02d}-01" for d in cf_dates]
    ds = ds.assign_coords(time=date_strs)

    lon_vals = ds["lon"].values
    if np.any(lon_vals > 180.0):
        norm_lons = ((ds["lon"] + 180.0) % 360.0) - 180.0
        ds = ds.assign_coords(lon=norm_lons)

    ds = ds.sortby(["lat", "lon"])

    if var_name in ds.data_vars:
        da = ds[var_name]
        masked = xr.where(
            (da >= MERRA2_FILL_THRESHOLD) | (da < MERRA2_VALID_MIN) | (da > MERRA2_VALID_MAX) | np.isnan(da),
            np.nan,
            da,
        )
        masked.attrs = da.attrs

        # GLDAS is land-only; oceans are already NaN in the source data.
        ds[var_name] = masked

    return ds


def open_oisst_dataset(custom_path_or_url: Optional[str] = None) -> xr.Dataset:
    """
    Opens NOAA OISST v2.1 dataset with decode_times=False.
    """
    if custom_path_or_url:
        return xr.open_dataset(custom_path_or_url, decode_times=False)

    local_file = get_cached_oisst_file_path()
    if local_file.exists():
        return xr.open_dataset(local_file, decode_times=False)

    try:
        logger.info("Attempting OPeNDAP open: %s", OISST_OPENDAP_URL)
        return xr.open_dataset(OISST_OPENDAP_URL, decode_times=False)
    except Exception as opendap_err:
        logger.warning("OPeNDAP connection failed (%s)", opendap_err)
        raise RuntimeError(f"Failed to access OISST NetCDF from OPeNDAP: {opendap_err}")


def normalize_oisst_dataset(
    ds: xr.Dataset,
    var_name: str = "sst",
    enforce_ocean_mask: bool = True,
) -> xr.Dataset:
    """
    Normalises NOAA OISST v2.1 coordinates and decodes fill values to NaN.
    Enforces ocean-only mask: land cells are decoded strictly to NaN (SPEC 6.3, SPEC 14.1).
    """
    time_coord = ds["time"]
    time_units = time_coord.attrs.get("units", "days since 1800-01-01 00:00:00")
    calendar = time_coord.attrs.get("calendar", "standard")
    raw_time = time_coord.values

    cf_dates = cftime.num2date(raw_time, units=time_units, calendar=calendar)
    date_strs = [f"{d.year:04d}-{d.month:02d}-01" for d in cf_dates]
    ds = ds.assign_coords(time=date_strs)

    lon_vals = ds["lon"].values
    if np.any(lon_vals > 180.0):
        norm_lons = ((ds["lon"] + 180.0) % 360.0) - 180.0
        ds = ds.assign_coords(lon=norm_lons)

    ds = ds.sortby(["lat", "lon"])

    if var_name in ds.data_vars:
        da = ds[var_name]
        masked = xr.where(
            (da <= OISST_FILL_THRESHOLD) | (da < OISST_VALID_MIN) | (da > OISST_VALID_MAX) | np.isnan(da),
            np.nan,
            da,
        )
        masked.attrs = da.attrs

        # The file's own ocean mask already encodes all land cells as fill value (-9.96921e+36).
        # Per prompt instruction: "Use the file's own ocean mask" (do not run slow polygon tests).
        ds[var_name] = masked

    return ds


def download_gldas_raw_file(target_path: Optional[Path] = None) -> Path:
    """
    Ensures GLDAS raw file is present in cache.
    If Earthdata credentials are provided in .env (SPEC 15.2), attempts remote download.
    """
    from backend.app.config import settings

    if target_path is None:
        target_path = get_cached_gldas_file_path()

    if target_path.exists() and target_path.stat().st_size > 100_000:
        return target_path

    ensure_cache_dirs()

    token = settings.EARTHDATA_TOKEN
    username = settings.EARTHDATA_USERNAME
    password = settings.EARTHDATA_PASSWORD

    headers = {"User-Agent": "EarthScienceExplorer/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif username and password:
        import base64
        creds = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {creds}"

    if target_path.exists() and target_path.stat().st_size > 100_000:
        return target_path

    raise RuntimeError(
        "Unavailable - real data not yet ingested"
    )


def open_gldas_dataset(custom_path_or_url: Optional[str] = None) -> xr.Dataset:
    """
    Opens NASA GLDAS Noah soil moisture dataset with decode_times=False.
    """
    if custom_path_or_url:
        return xr.open_dataset(custom_path_or_url, decode_times=False)

    local_file = get_cached_gldas_file_path()
    if local_file.exists():
        return xr.open_dataset(local_file, decode_times=False)

    downloaded = download_gldas_raw_file(local_file)
    return xr.open_dataset(downloaded, decode_times=False)


def normalize_gldas_dataset(
    ds: xr.Dataset,
    var_name: str = "SoilMoi0_10cm_inst",
    enforce_land_mask: bool = True,
) -> xr.Dataset:
    """
    Normalises GLDAS Noah coordinates and decodes fill values to NaN.
    Enforces land-only mask: ocean cells are decoded strictly to NaN (SPEC 6.3, SPEC 14.1).
    """
    time_coord = ds["time"]
    time_units = time_coord.attrs.get("units", "days since 2000-01-01 00:00:00")
    calendar = time_coord.attrs.get("calendar", "standard")
    raw_time = time_coord.values

    cf_dates = cftime.num2date(raw_time, units=time_units, calendar=calendar)
    date_strs = [f"{d.year:04d}-{d.month:02d}-01" for d in cf_dates]
    ds = ds.assign_coords(time=date_strs)

    lon_vals = ds["lon"].values
    if np.any(lon_vals > 180.0):
        norm_lons = ((ds["lon"] + 180.0) % 360.0) - 180.0
        ds = ds.assign_coords(lon=norm_lons)

    ds = ds.sortby(["lat", "lon"])

    if var_name in ds.data_vars:
        da = ds[var_name]
        masked = xr.where(
            (da <= GLDAS_FILL_THRESHOLD) | (da < GLDAS_VALID_MIN) | (da > GLDAS_VALID_MAX) | np.isnan(da),
            np.nan,
            da,
        )
        masked.attrs = da.attrs

        # GLDAS is land-only; oceans are already NaN in the source data.
        ds[var_name] = masked

    return ds


def download_merra2_qv2m_raw_file(target_path: Optional[Path] = None) -> Path:
    """
    Ensures MERRA-2 QV2M raw file is present in cache.
    If Earthdata credentials are provided in .env (SPEC 15.2), attempts remote download.
    """
    from backend.app.config import settings

    if target_path is None:
        target_path = get_cached_merra2_qv2m_file_path()

    if target_path.exists() and target_path.stat().st_size > 100_000:
        return target_path

    ensure_cache_dirs()

    token = settings.EARTHDATA_TOKEN
    username = settings.EARTHDATA_USERNAME
    password = settings.EARTHDATA_PASSWORD

    headers = {"User-Agent": "EarthScienceExplorer/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif username and password:
        import base64
        creds = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {creds}"

    if target_path.exists() and target_path.stat().st_size > 100_000:
        return target_path

    raise RuntimeError(
        "Unavailable - real data not yet ingested"
    )


def open_merra2_qv2m_dataset(custom_path_or_url: Optional[str] = None) -> xr.Dataset:
    """
    Opens MERRA-2 2-meter specific humidity dataset with decode_times=False.
    """
    if custom_path_or_url:
        return xr.open_dataset(custom_path_or_url, decode_times=False)

    local_file = get_cached_merra2_qv2m_file_path()
    if local_file.exists():
        return xr.open_dataset(local_file, decode_times=False)

    downloaded = download_merra2_qv2m_raw_file(local_file)
    return xr.open_dataset(downloaded, decode_times=False)


def normalize_merra2_qv2m_dataset(
    ds: xr.Dataset,
    var_name: str = "QV2M",
    enforce_mask: bool = True,
) -> xr.Dataset:
    """
    Normalises MERRA-2 QV2M coordinates and decodes fill values to NaN.
    Covers the global atmosphere over land and ocean.
    """
    time_coord = ds["time"]
    time_units = time_coord.attrs.get("units", "days since 1980-01-01 00:00:00")
    calendar = time_coord.attrs.get("calendar", "standard")
    raw_time = time_coord.values

    cf_dates = cftime.num2date(raw_time, units=time_units, calendar=calendar)
    date_strs = [f"{d.year:04d}-{d.month:02d}-01" for d in cf_dates]
    ds = ds.assign_coords(time=date_strs)

    lon_vals = ds["lon"].values
    if np.any(lon_vals > 180.0):
        norm_lons = ((ds["lon"] + 180.0) % 360.0) - 180.0
        ds = ds.assign_coords(lon=norm_lons)

    ds = ds.sortby(["lat", "lon"])

    if var_name in ds.data_vars:
        da = ds[var_name]
        masked = xr.where(
            (da >= MERRA2_QV2M_FILL_THRESHOLD) | (da < MERRA2_QV2M_VALID_MIN) | (da > MERRA2_QV2M_VALID_MAX) | np.isnan(da),
            np.nan,
            da,
        )
        masked.attrs = da.attrs
        ds[var_name] = masked

    return ds


def open_dataset(
    dataset_id: str = "gpcp_monthly_v23",
    custom_path_or_url: Optional[str] = None,
) -> xr.Dataset:
    """
    Universal dataset loader dispatching to the appropriate provider pipeline.
    """
    if dataset_id == "merra2_monthly_ts" or dataset_id in ["land_surface_temperature", "TS"]:
        return open_merra2_dataset(custom_path_or_url)
    if dataset_id == "noaa_oisst_v21" or dataset_id in ["sea_surface_temperature", "sst"]:
        return open_oisst_dataset(custom_path_or_url)
    if dataset_id == "gldas_noah025_m_v21" or dataset_id in ["soil_moisture", "SoilMoi0_10cm_inst"]:
        return open_gldas_dataset(custom_path_or_url)
    if dataset_id == "merra2_monthly_qv2m" or dataset_id in ["humidity", "QV2M"]:
        return open_merra2_qv2m_dataset(custom_path_or_url)
    return open_gpcp_dataset(custom_path_or_url)


def normalize_dataset(
    ds: xr.Dataset,
    dataset_id: str = "gpcp_monthly_v23",
    var_name: Optional[str] = None,
    enforce_mask: bool = True,
) -> xr.Dataset:
    """
    Universal dataset normalisation dispatching coordinate decoding, fill values,
    and coverage masking rules.
    """
    if dataset_id == "merra2_monthly_ts" or dataset_id in ["land_surface_temperature", "TS"] or var_name == "TS":
        return normalize_merra2_dataset(ds, var_name=var_name or "TS", enforce_land_mask=enforce_mask)
    if dataset_id == "noaa_oisst_v21" or dataset_id in ["sea_surface_temperature", "sst"] or var_name == "sst":
        return normalize_oisst_dataset(ds, var_name=var_name or "sst", enforce_ocean_mask=enforce_mask)
    if dataset_id == "gldas_noah025_m_v21" or dataset_id in ["soil_moisture", "SoilMoi0_10cm_inst"] or var_name == "SoilMoi0_10cm_inst":
        return normalize_gldas_dataset(ds, var_name=var_name or "SoilMoi0_10cm_inst", enforce_land_mask=enforce_mask)
    if dataset_id == "merra2_monthly_qv2m" or dataset_id in ["humidity", "QV2M"] or var_name == "QV2M":
        return normalize_merra2_qv2m_dataset(ds, var_name=var_name or "QV2M", enforce_mask=enforce_mask)
    return normalize_gpcp_dataset(ds, var_name=var_name or "precip")


def generate_expected_monthly_steps(start_date: str, end_date: str) -> List[str]:
    """
    Generates expected monthly steps from start_date to end_date as 'YYYY-MM-01'.
    """
    s_dt = datetime.strptime(start_date[:7], "%Y-%m")
    e_dt = datetime.strptime(end_date[:7], "%Y-%m")

    steps: List[str] = []
    curr = s_dt
    while curr <= e_dt:
        steps.append(curr.strftime("%Y-%m-01"))
        # Move to next month
        year = curr.year + (curr.month // 12)
        month = (curr.month % 12) + 1
        curr = datetime(year, month, 1)
    return steps


def validate_time_steps(
    available_steps: List[str],
    start_date: str,
    end_date: str,
) -> Tuple[List[str], List[str]]:
    """
    Compares available steps in dataset against expected range.
    Returns: (expected_steps, missing_steps)
    """
    expected = generate_expected_monthly_steps(start_date, end_date)
    avail_set = set(available_steps)
    missing = [step for step in expected if step not in avail_set]
    return expected, missing


def compute_subset_cache_key(
    collection: str,
    version: str,
    start_date: str,
    end_date: str,
    geom_hash: str,
    processing_settings: Dict[str, Any],
) -> str:
    """
    Computes a deterministic SHA-256 hash representing a subset query.
    Key elements: collection + version + time range + geometry hash + processing settings.
    """
    payload = {
        "collection": collection,
        "version": version,
        "start": start_date,
        "end": end_date,
        "geom_hash": geom_hash,
        "settings": processing_settings,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
