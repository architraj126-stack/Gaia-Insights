"""
Analysis Endpoints (SPEC 12.2, 12.3, 14, 15.1, 15.4, 16.3).

Endpoints:
- POST /api/analysis/timeseries: Execute or retrieve cached time-series analysis.
- GET /api/analysis/jobs/{job_id}: Query the status and progress of an analysis job.
- GET /api/results/series/{series_id}: Retrieve full time-series data, summary, and provenance.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import xarray as xr
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from shapely.geometry import box, shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import AnalysisOutput, AnalysisRun, DatasetProduct, Job
from backend.app.db.session import AsyncSessionLocal


async def get_db_session() -> Any:
    try:
        async with AsyncSessionLocal() as session:
            yield session
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Could not establish DB session: %s", e)
        raise
from backend.app.services.aggregate import (
    aggregate_annual,
    aggregate_monthly,
    aggregate_seasonal,
)
from backend.app.services.boundaries import get_boundary_by_id
from backend.app.services.ingest import (
    DATA_CACHE_DIR,
    SUBSET_CACHE_DIR,
    compute_subset_cache_key,
    normalize_gpcp_dataset,
    open_gpcp_dataset,
    open_dataset,
    normalize_dataset,
    validate_time_steps,
)
from backend.app.services.regions import extract_regional_mean_timeseries
from backend.app.services.trends import analyze_timeseries_trends
from backend.app.services.change import (
    OUTPUTS_DIR,
    execute_change_detection_analysis,
    inspect_change_cell,
)
from backend.app.services.significance import (
    execute_significance_analysis,
    reclassify_cached_significance,
)
from backend.app.config import settings
from backend.app.api.catalog import load_catalog_seed

logger = logging.getLogger("backend.api.analysis")

router = APIRouter(tags=["analysis"])

RESULTS_CACHE_DIR = DATA_CACHE_DIR / "results"
RESULTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
SUBSET_CACHE_DIR.mkdir(parents=True, exist_ok=True)

UNINGESTED_DATASET_IDS = {
    "merra2_monthly_ts",
    "gldas_noah025_m_v21",
    "merra2_monthly_qv2m",
}


def get_dataset_metadata_from_registry(dataset_id: str) -> Dict[str, Any]:
    """Retrieves dataset metadata from the catalog seed/registry."""
    variables = load_catalog_seed()
    for var in variables:
        for ds in var.datasets:
            if ds.id == dataset_id:
                return {
                    "id": ds.id,
                    "variable_id": ds.variable_id,
                    "start_date": ds.start_date,
                    "latest_observation_date": ds.latest_observation_date,
                    "version": ds.version,
                    "status": ds.status,
                }
    return {}


def get_dataset_latest_observation_date(dataset_id: str) -> Optional[str]:
    """Returns the latest observation date string (YYYY-MM-DD) for a dataset from the registry."""
    if dataset_id in UNINGESTED_DATASET_IDS:
        return None
    meta = get_dataset_metadata_from_registry(dataset_id)
    return meta.get("latest_observation_date")


def get_dataset_start_date(dataset_id: str) -> Optional[str]:
    """Returns the start date string (YYYY-MM-DD) for a dataset from the registry."""
    meta = get_dataset_metadata_from_registry(dataset_id)
    return meta.get("start_date")


def resolve_dataset_version(dataset_id: str, variable: Optional[str] = None, user_version: Optional[str] = None) -> str:
    """Resolve correct dataset version dynamically from catalog semantics (SPEC Rule 4)."""
    if user_version:
        return user_version
    ds_id = (dataset_id or "").lower()
    var = (variable or "").lower()
    if ds_id in ["merra2_monthly_ts", "merra2_monthly_qv2m"] or var in ["temperature", "land_surface_temperature", "humidity"]:
        return "5.12.4"
    if ds_id in ["noaa_oisst_v21"] or var in ["sea_surface_temperature", "sst"]:
        return "v2.1"
    if ds_id in ["gldas_noah025_m_v21"] or var in ["soil_moisture"]:
        return "2.1"
    return "v2.3"


def validate_geometry_input(geom_dict: Dict[str, Any]) -> BaseGeometry:
    """Validates geometry payload size, format, and spatial bounds (SPEC 16.2 Security)."""
    if not geom_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geometry must be provided.",
        )
    geom_str = json.dumps(geom_dict)
    if len(geom_str) > 2_000_000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Geometry payload exceeds size limit (maximum 2MB).",
        )
    try:
        geom_shape = shape(geom_dict)
        if not geom_shape.is_valid:
            geom_shape = geom_shape.buffer(0)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid geometry: {e}",
        )
    if geom_shape.is_empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geometry is empty.",
        )
    minx, miny, maxx, maxy = geom_shape.bounds
    if minx < -180.1 or maxx > 180.1 or miny < -90.1 or maxy > 90.1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Geometry bounds ({minx:.2f}, {miny:.2f}, {maxx:.2f}, {maxy:.2f}) exceed valid WGS84 range [-180, -90, 180, 90].",
        )
    return geom_shape


class TimeSeriesRequestOptions(BaseModel):
    area_weighted: bool = True
    include_missing_flags: bool = True
    trend_methods: List[str] = Field(default_factory=lambda: ["linear_regression", "sens_slope", "mann_kendall"])
    alpha: Optional[float] = None
    moving_average_window: Optional[int] = None
    simulate_gap_month: Optional[str] = None


class TimeSeriesRequest(BaseModel):
    dataset_id: str = "gpcp_monthly_v23"
    dataset_version: Optional[str] = None
    variable: str = "precipitation"
    region_id: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    geometry_crs: str = "EPSG:4326"
    start_date: str = "1990-01-01"
    end_date: str = "latest_complete"
    aggregation: str = "monthly"  # monthly | annual | seasonal
    options: TimeSeriesRequestOptions = Field(default_factory=TimeSeriesRequestOptions)


def _compute_geom_hash(geom_dict: Dict[str, Any]) -> str:
    raw = json.dumps(geom_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@router.post("/api/analysis/timeseries")
async def create_timeseries_analysis(
    req: TimeSeriesRequest,
    session: Optional[AsyncSession] = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    Executes or returns cached time-series analysis (SPEC 12.2 - 12.3).
    Area-weights regional means, applies scientific missing-data logic,
    and returns SPEC 15.4 provenance.
    """
    # SPEC 14.8 / Requirement 2: Reject uningested datasets
    if req.dataset_id in UNINGESTED_DATASET_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unavailable - real data not yet ingested",
        )

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    run_id = f"run_{uuid.uuid4().hex[:12]}"

    # 1. Resolve geometry
    region_name = "Custom Geometry"
    geom_dict = req.geometry

    if req.region_id:
        boundary = get_boundary_by_id(req.region_id)
        if not boundary or not boundary.get("geometry"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Region boundary '{req.region_id}' not found.",
            )
        geom_dict = boundary["geometry"]
        region_name = boundary.get("name") or req.region_id
    elif not geom_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'region_id' or 'geometry' must be provided.",
        )

    geom_shape = validate_geometry_input(geom_dict)
    geom_hash = _compute_geom_hash(geom_dict)

    # Fast cache check before any DB interaction
    dataset_version = resolve_dataset_version(req.dataset_id, req.variable, req.dataset_version)
    latest_obs = get_dataset_latest_observation_date(req.dataset_id)
    if req.end_date == "latest_complete":
        if not latest_obs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unavailable - real data not yet ingested",
            )
        end_date = latest_obs
    else:
        end_date = req.end_date
    proc_settings = {
        "aggregation": req.aggregation,
        "area_weighted": req.options.area_weighted,
        "variable": req.variable,
    }
    subset_key = compute_subset_cache_key(
        collection=req.dataset_id,
        version=dataset_version,
        start_date=req.start_date,
        end_date=end_date,
        geom_hash=geom_hash,
        processing_settings=proc_settings,
    )

    subset_cache_file = SUBSET_CACHE_DIR / f"{subset_key}.json"
    if subset_cache_file.exists():
        try:
            with open(subset_cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            logger.info("Serving analysis from cache: %s", subset_key)
            return cached_data["response"]
        except Exception as e:
            logger.warning("Failed to read cache file %s: %s", subset_cache_file, e)

    # 2. Resolve dataset metadata & latest observation date from DB if available
    if req.dataset_id == "merra2_monthly_ts":
        provider_source = "https://goldsmr4.gesdisc.eosdis.nasa.gov/opendap/MERRA2_MONTHLY/M2IMNXASM.5.12.4"
    elif req.dataset_id == "noaa_oisst_v21":
        provider_source = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc"
    elif req.dataset_id == "gldas_noah025_m_v21":
        provider_source = "https://opendap.earthdata.nasa.gov/collections/C1342986036-GES_DISC/granules/"
    else:
        provider_source = "https://psl.noaa.gov/thredds/dodsC/Datasets/gpcp/precip.mon.mean.nc"
    latest_obs_str = end_date

    if session:
        try:
            prod_stmt = select(DatasetProduct).where(DatasetProduct.id == req.dataset_id)
            res = await session.execute(prod_stmt)
            prod = res.scalar_one_or_none()
            if prod:
                dataset_version = prod.version or dataset_version
                provider_source = prod.access_url or provider_source
                if prod.latest_observation_date:
                    latest_obs_str = prod.latest_observation_date.strftime("%Y-%m-01")
        except Exception as e:
            logger.warning("Could not fetch dataset from DB: %s", e)
            try:
                await session.rollback()
            except Exception:
                pass
            session = None

    # Resolve end_date
    end_date = latest_obs_str if req.end_date == "latest_complete" else req.end_date

    # 4. Create Job in database
    db_job: Optional[Job] = None
    if session:
        try:
            db_job = Job(
                id=job_id,
                job_type="timeseries",
                status="running",
                percent_complete=10.0,
                messages=[{"time": datetime.now(timezone.utc).isoformat(), "text": "Starting ingestion"}],
                request_params=req.model_dump(),
            )
            session.add(db_job)
            await session.commit()
        except Exception as e:
            logger.warning("Failed to create initial DB job: %s", e)
            try:
                await session.rollback()
            except Exception:
                pass
            session = None

    is_merra2 = req.dataset_id == "merra2_monthly_ts" or req.variable in ["land_surface_temperature", "TS"]
    is_oisst = req.dataset_id == "noaa_oisst_v21" or req.variable in ["sea_surface_temperature", "sst"]
    is_gldas = req.dataset_id == "gldas_noah025_m_v21" or req.variable in ["soil_moisture", "SoilMoi0_10cm_inst"]
    is_humidity = req.dataset_id == "merra2_monthly_qv2m" or req.variable in ["humidity", "QV2M"]

    if is_merra2:
        target_var_field = "TS"
        coverage_type = "land_only"
    elif is_oisst:
        target_var_field = "sst"
        coverage_type = "ocean_only"
    elif is_gldas:
        target_var_field = "SoilMoi0_10cm_inst"
        coverage_type = "land_only"
    elif is_humidity:
        target_var_field = "QV2M"
        coverage_type = "global"
    else:
        target_var_field = "precip"
        coverage_type = "global"

    # 5. Open and process dataset
    try:
        ds_raw = open_dataset(dataset_id=req.dataset_id)
    except Exception as exc:
        err_msg = f"Data source unreachable: {exc}"
        logger.error(err_msg)
        if session and db_job:
            db_job.status = "failed"
            db_job.error_detail = err_msg
            await session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=err_msg,
        )

    try:
        ds_norm = normalize_dataset(ds_raw, dataset_id=req.dataset_id, var_name=target_var_field, enforce_mask=True)
    except Exception as exc:
        err_msg = f"Failed to normalise dataset coordinates or mask values: {exc}"
        logger.error(err_msg)
        if session and db_job:
            db_job.status = "failed"
            db_job.error_detail = err_msg
            await session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=err_msg,
        )

    # Check available time coordinate in dataset
    all_time_steps = [str(t)[:10] for t in ds_norm["time"].values]
    expected_steps, missing_steps = validate_time_steps(
        all_time_steps, req.start_date, end_date
    )

    # Filter to requested time range
    time_mask = (ds_norm["time"] >= req.start_date) & (ds_norm["time"] <= end_date)
    ds_time_slice = ds_norm.sel(time=time_mask)

    if ds_time_slice["time"].size == 0:
        err_msg = f"No data found in requested range {req.start_date} to {end_date}."
        if session and db_job:
            db_job.status = "failed"
            db_job.error_detail = err_msg
            await session.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=err_msg,
        )

    # Spatial slicing: slice bounding box with buffer
    minx, miny, maxx, maxy = geom_shape.bounds
    buf = 3.0  # buffer in degrees for grid margin
    lat_min = max(-90.0, miny - buf)
    lat_max = min(90.0, maxy + buf)
    lon_min = max(-180.0, minx - buf)
    lon_max = min(180.0, maxx + buf)

    ds_spatial = ds_time_slice.sel(
        lat=slice(lat_min, lat_max),
        lon=slice(lon_min, lon_max),
    )

    # If bounding box slice is empty, fall back to full extent
    if ds_spatial["lat"].size == 0 or ds_spatial["lon"].size == 0:
        ds_spatial = ds_time_slice

    # 6. Extract regional mean time series
    mask_method = "fractional_overlap" if req.options.area_weighted else "cell_centre"
    spatial_result = extract_regional_mean_timeseries(
        ds_spatial[target_var_field],
        geom_shape,
        method=mask_method,
        coverage_type=coverage_type,
    )

    # Align with expected monthly steps so any missing time step becomes an honest gap
    step_dict = {
        t: (m, c, a)
        for t, m, c, a in zip(
            spatial_result["time_steps"],
            spatial_result["mean_values"],
            spatial_result["valid_cell_counts"],
            spatial_result["valid_areas_km2"],
        )
    }

    aligned_time_steps = []
    aligned_mean_values = []
    aligned_valid_counts = []
    aligned_valid_areas = []

    for step in expected_steps:
        aligned_time_steps.append(step)
        if req.options.simulate_gap_month and step == req.options.simulate_gap_month:
            aligned_mean_values.append(None)
            aligned_valid_counts.append(0)
            aligned_valid_areas.append(0.0)
            if step not in missing_steps:
                missing_steps.append(step)
        elif step in step_dict:
            m, c, a = step_dict[step]
            aligned_mean_values.append(m)
            aligned_valid_counts.append(c)
            aligned_valid_areas.append(a)
        else:
            aligned_mean_values.append(None)
            aligned_valid_counts.append(0)
            aligned_valid_areas.append(0.0)

    is_merra2 = req.dataset_id == "merra2_monthly_ts" or req.variable in ["land_surface_temperature", "TS"]

    # 7. Temporal Aggregation
    if req.aggregation == "annual":
        monthly_pts = aggregate_monthly(
            aligned_time_steps,
            aligned_mean_values,
            aligned_valid_counts,
            aligned_valid_areas,
            variable=req.variable,
        )
        final_series_points = aggregate_annual(monthly_pts, variable=req.variable)
        output_units = "°C" if (is_merra2 or is_oisst) else ("kg/m²" if is_gldas else ("g/kg" if is_humidity else ("mm" if req.variable == "precipitation" else "native")))
    elif req.aggregation == "seasonal":
        monthly_pts = aggregate_monthly(
            aligned_time_steps,
            aligned_mean_values,
            aligned_valid_counts,
            aligned_valid_areas,
            variable=req.variable,
        )
        final_series_points = aggregate_seasonal(monthly_pts, variable=req.variable)
        output_units = "°C" if (is_merra2 or is_oisst) else ("kg/m²" if is_gldas else ("g/kg" if is_humidity else ("mm" if req.variable == "precipitation" else "native")))
    else:  # monthly
        final_series_points = aggregate_monthly(
            aligned_time_steps,
            aligned_mean_values,
            aligned_valid_counts,
            aligned_valid_areas,
            variable=req.variable,
        )
        output_units = "°C" if (is_merra2 or is_oisst) else ("kg/m²" if is_gldas else ("g/kg" if is_humidity else ("mm" if req.variable == "precipitation" else "mm/day")))

    # 8. Compute trend & summary statistics
    final_series_points, trend_summary = analyze_timeseries_trends(
        points=final_series_points,
        aggregation=req.aggregation,
        variable=req.variable,
        alpha=req.options.alpha or settings.TREND_ALPHA,
        min_data_points=settings.TREND_MIN_DATA_POINTS,
        moving_avg_window=req.options.moving_average_window,
        expected_total_steps=len(expected_steps),
    )
    valid_steps_count = trend_summary["valid_n"]
    expected_steps_count = trend_summary["expected_n"]
    completeness_pct = trend_summary["completeness"]["pct"]

    warnings: List[str] = []
    if len(missing_steps) > 0:
        warnings.append(f"Missing time steps in observation record: {len(missing_steps)} months.")
    if completeness_pct < 100.0:
        warnings.append(f"Dataset completeness is {completeness_pct}%.")

    # 9. Assemble SPEC 15.4 Provenance
    if is_merra2:
        prov_provider = "NASA GES DISC / GMAO"
        prov_doi = "10.5067/5ESKGQTZG7FO"
        prov_field = "TS"
        prov_units = "K"
        prov_conversion = "°C = K - 273.15"
    elif is_oisst:
        prov_provider = "NOAA NCEI / PSL"
        prov_doi = "10.25921/RE9P-PT57"
        prov_field = "sst"
        prov_units = "degC"
        prov_conversion = "native (°C)"
    elif is_gldas:
        prov_provider = "NASA GES DISC"
        prov_doi = "10.5067/SXAVCZFAQLNO"
        prov_field = "SoilMoi0_10cm_inst"
        prov_units = "kg m-2"
        prov_conversion = "native (kg/m² = 1 mm water equivalent)"
    elif is_humidity:
        prov_provider = "NASA GES DISC / GMAO"
        prov_doi = "10.5067/AP1B0BA5PD2K"
        prov_field = "QV2M"
        prov_units = "kg kg-1"
        prov_conversion = "g/kg = kg/kg * 1000.0"
    else:
        prov_provider = "NOAA PSL / NCEI"
        prov_doi = "10.7289/V56971W2"
        prov_field = "precip"
        prov_units = "mm/day"
        prov_conversion = "rate * days_in_month" if req.variable == "precipitation" and req.aggregation == "monthly" else "sum_of_12_months" if req.aggregation == "annual" else "none"

    provenance = {
        "provider": prov_provider,
        "collection_id": req.dataset_id,
        "product_version": dataset_version,
        "doi": prov_doi,
        "native_field": prov_field,
        "native_units": prov_units,
        "output_units": output_units,
        "scale_offset": {"scale_factor": 1.0, "add_offset": 0.0},
        "conversion_applied": prov_conversion,
        "actual_start": spatial_result["time_steps"][0] if spatial_result["time_steps"] else req.start_date,
        "actual_end": spatial_result["time_steps"][-1] if spatial_result["time_steps"] else end_date,
        "valid_steps_count": valid_steps_count,
        "expected_steps_count": expected_steps_count,
        "completeness_pct": completeness_pct,
        "missing_steps": missing_steps,
        "region_id": req.region_id,
        "region_name": region_name,
        "geometry_hash": geom_hash,
        "geometry_crs": req.geometry_crs,
        "spatial_mask_method": spatial_result["mask_method"],
        "area_weighting": spatial_result["area_weighting"],
        "total_region_area_km2": spatial_result["total_region_area_km2"],
        "intersecting_cells": spatial_result["intersecting_cell_count"],
        "aggregation_method": req.aggregation,
        "trend_method": "OLS linear regression, Theil-Sen estimator, Mann-Kendall, Hamed-Rao modified MK",
        "code_version": "0.1.0",
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    # 10. Persist Output Artefacts and Response
    series_id = f"series_{run_id}"
    series_result_file = RESULTS_CACHE_DIR / f"{series_id}.json"

    full_result_payload = {
        "series_id": series_id,
        "run_id": run_id,
        "job_id": job_id,
        "dataset": {
            "id": req.dataset_id,
            "version": dataset_version,
            "variable": req.variable,
            "units": output_units,
            "source": provider_source,
        },
        "coverage": {
            "requested_start": req.start_date,
            "actual_start": provenance["actual_start"],
            "actual_end": provenance["actual_end"],
            "valid_steps": valid_steps_count,
            "expected_steps": expected_steps_count,
            "completeness_pct": completeness_pct,
        },
        "points": final_series_points,
        "summary": trend_summary,
        "provenance": provenance,
        "warnings": warnings,
    }

    with open(series_result_file, "w", encoding="utf-8") as f:
        json.dump(full_result_payload, f)

    # SPEC 12.3 response shape
    spec_response = {
        "job_id": job_id,
        "run_id": run_id,
        "series_id": series_id,
        "status": "completed",
        "dataset": {
            "id": req.dataset_id,
            "version": dataset_version,
            "units": output_units,
            "source": provider_source,
        },
        "coverage": full_result_payload["coverage"],
        "series_url": f"/api/results/series/{series_id}",
        "points": final_series_points,
        "summary": trend_summary,
        "warnings": warnings,
    }

    # Save to subset cache for instant second-call retrieval
    with open(subset_cache_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "cache_key": subset_key,
                "response": spec_response,
                "full_result_file": str(series_result_file),
            },
            f,
        )

    # Update database records (AnalysisRun, AnalysisOutput, Job)
    if session:
        try:
            db_run = AnalysisRun(
                id=run_id,
                run_type="timeseries",
                dataset_id=req.dataset_id,
                dataset_version=dataset_version,
                request_params=req.model_dump(),
                status="completed",
                warnings=warnings,
                completed_at=datetime.now(timezone.utc),
            )
            session.add(db_run)

            db_output = AnalysisOutput(
                id=series_id,
                run_id=run_id,
                output_type="series",
                file_path=str(series_result_file),
                summary=trend_summary,
                provenance=provenance,
                output_units=output_units,
            )
            session.add(db_output)

            if db_job:
                db_job.status = "completed"
                db_job.percent_complete = 100.0
                db_job.result_url = spec_response["series_url"]
                db_job.completed_at = datetime.now(timezone.utc)

            await session.commit()
        except Exception as e:
            logger.warning("Failed to persist analysis run to DB: %s", e)

    return spec_response


@router.get("/api/analysis/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    session: Optional[AsyncSession] = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    Returns the status and progress of an analysis job (SPEC 12.4).
    """
    if session:
        try:
            stmt = select(Job).where(Job.id == job_id)
            res = await session.execute(stmt)
            job = res.scalar_one_or_none()
            if job:
                return {
                    "job_id": job.id,
                    "job_type": job.job_type,
                    "status": job.status,
                    "percent_complete": job.percent_complete,
                    "messages": job.messages or [],
                    "result_url": job.result_url,
                    "error_detail": job.error_detail,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                }
        except Exception as e:
            logger.warning("Error fetching job %s from DB: %s", job_id, e)

    return {
        "job_id": job_id,
        "status": "completed",
        "percent_complete": 100.0,
        "messages": [],
        "result_url": f"/api/results/series/series_{job_id.replace('job_', 'run_')}",
    }


@router.get("/api/results/series/{series_id}")
async def get_series_result(
    series_id: str,
    session: Optional[AsyncSession] = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    Retrieves full time series points, coverage, summary, and SPEC 15.4 provenance.
    """
    # 1. Try file cache directly
    series_file = RESULTS_CACHE_DIR / f"{series_id}.json"
    if series_file.exists():
        try:
            with open(series_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to read series file %s: %s", series_file, e)

    # 2. Try DB lookup
    if session:
        try:
            stmt = select(AnalysisOutput).where(AnalysisOutput.id == series_id)
            res = await session.execute(stmt)
            out = res.scalar_one_or_none()
            if out and out.file_path and Path(out.file_path).exists():
                with open(out.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("Error querying AnalysisOutput from DB: %s", e)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Time-series result '{series_id}' not found.",
    )


# ---------------------------------------------------------------------------
# Phase 5: Change Detection Endpoints (SPEC 9, 14.5, 14.8)
# ---------------------------------------------------------------------------

class ChangeMapRequest(BaseModel):
    dataset_id: str = "gpcp_monthly_v23"
    dataset_version: Optional[str] = None
    variable: str = "precipitation"
    region_id: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    geometry_crs: str = "EPSG:4326"
    baseline_period: Optional[List[int]] = None
    comparison_period: Optional[List[int]] = None
    metric: str = "absolute"  # absolute | percentage | spatial_trend
    aggregation: str = "annual"  # annual | monthly
    epsilon: float = 1.0  # For percentage change
    allow_overlap: bool = False


class CellInspectRequest(BaseModel):
    run_id: str
    lat: float
    lon: float


@router.post("/api/analysis/change-map")
async def create_change_map_analysis(
    req: ChangeMapRequest,
    session: Optional[AsyncSession] = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    Executes or returns cached change detection analysis (SPEC 9, 14.5).
    Tracks execution in the jobs table with full provenance (SPEC 15.4).
    """
    # SPEC 14.8 / Requirement 2: Reject uningested datasets
    if req.dataset_id in UNINGESTED_DATASET_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unavailable - real data not yet ingested",
        )

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    run_id = f"run_{uuid.uuid4().hex[:12]}"

    # Derive baseline and comparison periods if not provided
    latest_obs = get_dataset_latest_observation_date(req.dataset_id)
    if not latest_obs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unavailable - real data not yet ingested",
        )
    obs_year = int(latest_obs[:4])
    obs_month = int(latest_obs[5:7])
    last_complete_year = obs_year if obs_month == 12 else obs_year - 1

    comparison_period = req.comparison_period
    if not comparison_period:
        comp_end = last_complete_year
        comp_start = comp_end - 19
        comparison_period = [comp_start, comp_end]

    baseline_period = req.baseline_period
    if not baseline_period:
        ds_start = get_dataset_start_date(req.dataset_id) or "1979-01-01"
        ds_start_year = int(ds_start[:4])
        base_end = comparison_period[0] - 1
        base_start = max(ds_start_year, base_end - 15)
        baseline_period = [base_start, base_end]

    # 1. Resolve geometry
    geom_dict = req.geometry
    region_name = "Custom Geometry"

    if req.region_id:
        boundary = get_boundary_by_id(req.region_id)
        if not boundary or not boundary.get("geometry"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Region boundary '{req.region_id}' not found.",
            )
        geom_dict = boundary["geometry"]
        region_name = boundary.get("name") or req.region_id
    elif not geom_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'region_id' or 'geometry' must be provided.",
        )

    geom_shape = validate_geometry_input(geom_dict)

    if len(baseline_period) != 2 or len(comparison_period) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both baseline_period and comparison_period must have [start_year, end_year].",
        )

    # 2. Check overlap
    if not req.allow_overlap:
        b_s, b_e = baseline_period
        c_s, c_e = comparison_period
        if max(b_s, c_s) <= min(b_e, c_e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Baseline period [{b_s}-{b_e}] and comparison period [{c_s}-{c_e}] overlap. "
                    "Overlapping periods must be explicitly confirmed."
                ),
            )

    # 3. Cache check
    geom_hash = _compute_geom_hash(geom_dict)
    cache_payload = {
        "dataset_id": req.dataset_id,
        "variable": req.variable,
        "baseline_period": baseline_period,
        "comparison_period": comparison_period,
        "metric": req.metric,
        "aggregation": req.aggregation,
        "epsilon": req.epsilon,
        "geom_hash": geom_hash,
    }
    change_key = hashlib.sha256(
        json.dumps(cache_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]

    cached_run_file = OUTPUTS_DIR / f"result_{change_key}.json"
    if cached_run_file.exists():
        try:
            with open(cached_run_file, "r", encoding="utf-8") as f:
                cached_res = json.load(f)
            logger.info("Serving change map from cache: %s", change_key)
            return cached_res
        except Exception as e:
            logger.warning("Failed to read cached change map: %s", e)

    # 4. Create Job in database
    db_job: Optional[Job] = None
    if session:
        try:
            db_job = Job(
                id=job_id,
                job_type="change_map",
                status="running",
                percent_complete=15.0,
                messages=[{"time": datetime.now(timezone.utc).isoformat(), "text": "Starting change map analysis"}],
                request_params=req.model_dump(),
            )
            session.add(db_job)
            await session.commit()
        except Exception as e:
            logger.warning("Failed to create initial DB job: %s", e)
            try:
                await session.rollback()
            except Exception:
                pass
            session = None

    # 5. Open & normalise dataset
    target_var_field = "TS" if (req.dataset_id == "merra2_monthly_ts" or req.variable in ["land_surface_temperature", "TS"]) else "precip"
    try:
        ds_raw = open_dataset(dataset_id=req.dataset_id)
        ds_norm = normalize_dataset(ds_raw, dataset_id=req.dataset_id, var_name=target_var_field, enforce_mask=True)
    except Exception as exc:
        err_msg = f"Failed to open or normalize dataset: {exc}"
        logger.error(err_msg)
        if session and db_job:
            db_job.status = "failed"
            db_job.error_detail = err_msg
            await session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=err_msg,
        )

    # 6. Execute change detection analysis
    try:
        da = ds_norm[target_var_field]
        result = execute_change_detection_analysis(
            data_array=da,
            geometry=geom_shape,
            baseline_years=(baseline_period[0], baseline_period[1]),
            comparison_years=(comparison_period[0], comparison_period[1]),
            variable=req.variable,
            metric=req.metric,
            aggregation=req.aggregation,
            epsilon=req.epsilon,
            allow_overlap=req.allow_overlap,
            run_id=run_id,
            output_dir=OUTPUTS_DIR,
        )
    except ValueError as ve:
        err_msg = str(ve)
        logger.warning("Change detection validation failed: %s", err_msg)
        if session and db_job:
            db_job.status = "failed"
            db_job.error_detail = err_msg
            await session.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as exc:
        err_msg = f"Change detection analysis failed: {exc}"
        logger.error(err_msg)
        if session and db_job:
            db_job.status = "failed"
            db_job.error_detail = err_msg
            await session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=err_msg,
        )

    response = {
        "job_id": job_id,
        "run_id": run_id,
        "status": "completed",
        "overlay_url": result["overlay_url"],
        "geotiff_url": f"/api/analysis/change-map/{run_id}/geotiff",
        "bounds": result["bounds"],
        "legend": result["legend"],
        "spatial_summary": result["spatial_summary"],
        "provenance": result["provenance"],
        "warnings": result["warnings"],
        "units": result["units"],
        "metric": result["metric"],
    }

    # Save cache file with change_key and run_id
    with open(cached_run_file, "w", encoding="utf-8") as f:
        json.dump(response, f)
    with open(OUTPUTS_DIR / f"result_{run_id}.json", "w", encoding="utf-8") as f:
        json.dump(response, f)

    # 7. Update Job & save AnalysisRun/Output in DB
    if session:
        try:
            analysis_run = AnalysisRun(
                id=run_id,
                session_id=None,
                run_type="change_map",
                dataset_id=req.dataset_id,
                dataset_version=resolve_dataset_version(req.dataset_id, req.variable, req.dataset_version),
                request_params=req.model_dump(),
                status="completed",
                warnings=result["warnings"],
                completed_at=datetime.now(timezone.utc),
            )
            session.add(analysis_run)

            analysis_output = AnalysisOutput(
                id=f"change_{run_id}",
                run_id=run_id,
                output_type="raster",
                file_path=result["provenance"].get("geotiff_path"),
                summary=result["spatial_summary"],
                provenance=result["provenance"],
                output_units=result["units"],
            )
            session.add(analysis_output)

            if db_job:
                db_job.status = "completed"
                db_job.percent_complete = 100.0
                db_job.result_url = f"/api/analysis/change-map/{run_id}"
                db_job.completed_at = datetime.now(timezone.utc)

            await session.commit()
        except Exception as e:
            logger.warning("Failed to save AnalysisRun/Job in DB: %s", e)

    return response


@router.get("/api/analysis/change-map/{run_id}")
async def get_change_map_result(run_id: str) -> Dict[str, Any]:
    """Retrieves cached change detection result for a run_id."""
    res_file = OUTPUTS_DIR / f"result_{run_id}.json"
    if res_file.exists():
        with open(res_file, "r", encoding="utf-8") as f:
            return json.load(f)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Change detection run '{run_id}' not found.",
    )


@router.get("/api/analysis/change-map/{run_id}/geotiff")
async def download_change_geotiff(run_id: str) -> FileResponse:
    """Downloads the georeferenced GeoTIFF for a change detection run."""
    tif_file = OUTPUTS_DIR / f"change_{run_id}.tif"
    if tif_file.exists():
        return FileResponse(
            path=str(tif_file),
            media_type="image/tiff",
            filename=f"change_{run_id}.tif",
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"GeoTIFF for run '{run_id}' not found.",
    )


@router.get("/api/analysis/change-map/{run_id}/overlay.png")
async def get_change_overlay_png(run_id: str) -> FileResponse:
    """Serves the transparent PNG map overlay for a change detection run."""
    png_file = OUTPUTS_DIR / f"overlay_{run_id}.png"
    if png_file.exists():
        return FileResponse(
            path=str(png_file),
            media_type="image/png",
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Map overlay PNG for run '{run_id}' not found.",
    )


@router.get("/api/analysis/change-map/{run_id}/inspect")
async def inspect_cell_get(
    run_id: str,
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
) -> Dict[str, Any]:
    """Inspects cell values (baseline, comparison, difference) at lat/lon via GET."""
    try:
        return inspect_change_cell(run_id=run_id, target_lat=lat, target_lon=lon, output_dir=OUTPUTS_DIR)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to inspect cell: {e}",
        )


@router.post("/api/analysis/change-map/inspect")
async def inspect_cell_post(req: CellInspectRequest) -> Dict[str, Any]:
    """Inspects cell values (baseline, comparison, difference) at lat/lon via POST."""
    try:
        return inspect_change_cell(run_id=req.run_id, target_lat=req.lat, target_lon=req.lon, output_dir=OUTPUTS_DIR)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{req.run_id}' not found.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to inspect cell: {e}",
        )


# ---------------------------------------------------------------------------
# Phase 6a: Statistical Significance Endpoints (SPEC 10, 14.6, 14.7)
# ---------------------------------------------------------------------------

class SignificanceRequest(BaseModel):
    series_id: Optional[str] = None
    change_run_id: Optional[str] = None
    dataset_id: str = "gpcp_monthly_v23"
    dataset_version: Optional[str] = None
    variable: str = "precipitation"
    region_id: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    geometry_crs: str = "EPSG:4326"
    mode: str = "both"  # regional | spatial | both
    alpha: float = 0.05
    ci_level: float = 0.95
    autocorrelation_method: str = "auto"  # auto | hamed_rao | pre_whitening | none
    fdr_correction: bool = True
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    reclassify_run_id: Optional[str] = None


@router.post("/api/analysis/significance")
async def create_significance_analysis(
    req: SignificanceRequest,
    session: Optional[AsyncSession] = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    Evaluates trend statistical significance (SPEC 10.3 - 10.6).
    Re-reads time series data from cache (never infers significance from difference raster).
    Supports rapid reclassification of alpha / FDR options without re-running regressions.
    """
    # SPEC 14.8 / Requirement 2: Reject uningested datasets
    if req.dataset_id in UNINGESTED_DATASET_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unavailable - real data not yet ingested",
        )

    # 1. Fast reclassification if reclassify_run_id is specified
    if req.reclassify_run_id:
        try:
            return reclassify_cached_significance(
                run_id=req.reclassify_run_id,
                alpha=req.alpha,
                fdr_correction=req.fdr_correction,
                output_dir=OUTPUTS_DIR,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Spatial cache for run '{req.reclassify_run_id}' not found.",
            )

    job_id = f"job_sig_{uuid.uuid4().hex[:10]}"
    run_id = f"sig_{uuid.uuid4().hex[:10]}"

    # Derive start_year and end_year if not specified
    latest_obs = get_dataset_latest_observation_date(req.dataset_id)
    if not latest_obs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unavailable - real data not yet ingested",
        )
    obs_year = int(latest_obs[:4])
    obs_month = int(latest_obs[5:7])
    last_complete_year = obs_year if obs_month == 12 else obs_year - 1

    end_year = req.end_year if req.end_year is not None else last_complete_year
    ds_start = get_dataset_start_date(req.dataset_id) or "1979-01-01"
    ds_start_year = int(ds_start[:4])
    start_year = req.start_year if req.start_year is not None else max(ds_start_year, 1990)

    # 2. Resolve geometry
    geom_dict = req.geometry
    if req.region_id:
        boundary = get_boundary_by_id(req.region_id)
        if not boundary or not boundary.get("geometry"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Region boundary '{req.region_id}' not found.",
            )
        geom_dict = boundary["geometry"]
    elif not geom_dict:
        # Check if we can infer geometry from Page 4 run
        if req.change_run_id:
            c_file = OUTPUTS_DIR / f"result_{req.change_run_id}.json"
            if c_file.exists():
                with open(c_file, "r", encoding="utf-8") as f:
                    c_data = json.load(f)
                    bounds = c_data.get("bounds")
                    if bounds:
                        geom_dict = box(bounds[0][1], bounds[0][0], bounds[1][1], bounds[1][0]).__geo_interface__

    if not geom_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'region_id', 'geometry', or valid 'change_run_id' must be provided.",
        )

    geom_shape = validate_geometry_input(geom_dict)

    # 3. Retrieve Page 3 regional series points if available
    time_series_points = None
    if req.series_id:
        series_file = RESULTS_CACHE_DIR / f"{req.series_id}.json"
        if series_file.exists():
            try:
                with open(series_file, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                    time_series_points = s_data.get("points")
            except Exception as e:
                logger.warning("Failed to read series file: %s", e)

    # 4. Open dataset for spatial testing
    da = None
    is_merra2 = req.dataset_id == "merra2_monthly_ts" or req.variable in ["land_surface_temperature", "TS"]
    is_oisst = req.dataset_id == "noaa_oisst_v21" or req.variable in ["sea_surface_temperature", "sst"]
    is_gldas = req.dataset_id == "gldas_noah025_m_v21" or req.variable in ["soil_moisture", "SoilMoi0_10cm_inst"]
    is_humidity = req.dataset_id == "merra2_monthly_qv2m" or req.variable in ["humidity", "QV2M"]

    if is_merra2:
        target_var_field = "TS"
        coverage_type = "land_only"
    elif is_oisst:
        target_var_field = "sst"
        coverage_type = "ocean_only"
    elif is_gldas:
        target_var_field = "SoilMoi0_10cm_inst"
        coverage_type = "land_only"
    elif is_humidity:
        target_var_field = "QV2M"
        coverage_type = "global"
    else:
        target_var_field = "precip"
        coverage_type = "global"
    if req.mode in ["spatial", "both"]:
        try:
            ds_raw = open_dataset(dataset_id=req.dataset_id)
            ds_norm = normalize_dataset(ds_raw, dataset_id=req.dataset_id, var_name=target_var_field, enforce_mask=True)
            da = ds_norm[target_var_field]
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to access underlying dataset for spatial significance: {exc}",
            )

    # If regional mode requested but series_id was not provided, extract regional series
    if req.mode in ["regional", "both"] and not time_series_points and da is not None:
        try:
            reg_series = extract_regional_mean_timeseries(da, geom_shape, coverage_type=coverage_type)
            time_series_points = aggregate_monthly(
                time_steps=reg_series["time_steps"],
                mean_rates=reg_series["mean_values"],
                valid_counts=reg_series["valid_cell_counts"],
                valid_areas=reg_series["valid_areas_km2"],
                variable=req.variable,
            )
        except Exception as e:
            logger.warning("Could not auto-generate regional points: %s", e)

    # 5. Execute Significance Analysis
    years = list(range(start_year, end_year + 1))
    try:
        result = execute_significance_analysis(
            data_array=da,
            geometry=geom_shape,
            time_series_points=time_series_points,
            years=years,
            variable=req.variable,
            mode=req.mode,
            alpha=req.alpha,
            ci_level=req.ci_level,
            autocorrelation_method=req.autocorrelation_method,
            fdr_correction=req.fdr_correction,
            run_id=run_id,
            output_dir=OUTPUTS_DIR,
        )
    except Exception as exc:
        logger.error("Significance analysis failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Significance analysis failed: {exc}",
        )

    # 6. Save result JSON
    with open(OUTPUTS_DIR / f"significance_result_{run_id}.json", "w", encoding="utf-8") as f:
        json.dump(result, f)

    # 7. Persist to DB
    if session:
        try:
            db_job = Job(
                id=job_id,
                job_type="significance",
                status="completed",
                percent_complete=100.0,
                result_url=f"/api/analysis/significance/{run_id}",
                request_params=req.model_dump(),
                completed_at=datetime.now(timezone.utc),
            )
            session.add(db_job)

            analysis_run = AnalysisRun(
                id=run_id,
                run_type="significance",
                dataset_id=req.dataset_id,
                dataset_version=resolve_dataset_version(req.dataset_id, req.variable, req.dataset_version),
                request_params=req.model_dump(),
                status="completed",
                completed_at=datetime.now(timezone.utc),
            )
            session.add(analysis_run)

            await session.commit()
        except Exception as e:
            logger.warning("Failed to record significance run to DB: %s", e)

    return result


@router.get("/api/analysis/significance/{run_id}")
async def get_significance_result(run_id: str) -> Dict[str, Any]:
    """Retrieves cached significance result for a run_id."""
    res_file = OUTPUTS_DIR / f"significance_result_{run_id}.json"
    if res_file.exists():
        with open(res_file, "r", encoding="utf-8") as f:
            return json.load(f)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Significance run '{run_id}' not found.",
    )


@router.get("/api/analysis/significance/{run_id}/geotiff")
async def download_significance_geotiff(run_id: str) -> FileResponse:
    """Downloads the 5-class GeoTIFF for a significance run."""
    tif_file = OUTPUTS_DIR / f"significance_{run_id}.tif"
    if tif_file.exists():
        return FileResponse(
            path=str(tif_file),
            media_type="image/tiff",
            filename=f"significance_{run_id}.tif",
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"GeoTIFF for significance run '{run_id}' not found.",
    )


@router.get("/api/analysis/significance/{run_id}/overlay.png")
async def get_significance_overlay_png(run_id: str) -> FileResponse:
    """Serves the transparent PNG map overlay for a significance run."""
    png_file = OUTPUTS_DIR / f"significance_overlay_{run_id}.png"
    if png_file.exists():
        return FileResponse(
            path=str(png_file),
            media_type="image/png",
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Map overlay PNG for significance run '{run_id}' not found.",
    )
