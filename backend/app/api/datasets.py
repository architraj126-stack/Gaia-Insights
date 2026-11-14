import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.services.availability import check_dataset_availability

router = APIRouter(prefix="/api/datasets", tags=["Datasets"])


class ValidDateRange(BaseModel):
    start: Optional[str] = None
    latest_observation_date: Optional[str] = None
    last_catalogue_check: Optional[str] = None


class AvailabilityResponse(BaseModel):
    dataset_id: str
    variable_id: str
    product_name: str
    version: str
    status: str
    spatial_coverage_percent: float
    temporal_coverage_percent: float
    cell_count: int
    spatial_resolution: str
    temporal_resolution: str
    area_km2: float
    valid_date_range: Dict[str, Any]
    warnings: List[str]
    provider: str
    citation: Optional[str] = None


class AvailabilityCheckRequest(BaseModel):
    geometry: Optional[Dict[str, Any]] = None
    bbox: Optional[List[float]] = None
    start: Optional[str] = None
    end: Optional[str] = None


@router.get("/{dataset_id}/availability", response_model=AvailabilityResponse)
async def get_dataset_availability(
    dataset_id: str,
    start: Optional[str] = Query(None, description="Start date ISO string (e.g. 1990-01-01)"),
    end: Optional[str] = Query(None, description="End date ISO string (e.g. 2020-12-31)"),
    bbox: Optional[str] = Query(None, description="Bounding box as minx,miny,maxx,maxy"),
    geometry: Optional[str] = Query(None, description="Serialized GeoJSON geometry string"),
) -> AvailabilityResponse:
    """
    Computes spatial and temporal availability coverage for a dataset given a region geometry or bbox,
    evaluating grid cell size, cell center counts, and date bounds.
    """
    geom_dict = None
    if geometry:
        try:
            geom_dict = json.loads(geometry)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid geometry JSON query: {e}")

    bbox_list = None
    if bbox:
        try:
            bbox_list = [float(x.strip()) for x in bbox.split(",")]
            if len(bbox_list) != 4:
                raise ValueError("bbox must contain exactly 4 comma-separated numbers")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid bbox parameter: {e}")

    try:
        res = check_dataset_availability(
            dataset_id=dataset_id,
            geometry=geom_dict,
            bbox=bbox_list,
            start=start,
            end=end,
        )
        return AvailabilityResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e).lower() else 400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Availability check failed: {e}")


@router.post("/{dataset_id}/availability", response_model=AvailabilityResponse)
async def post_dataset_availability(
    dataset_id: str,
    req: AvailabilityCheckRequest,
) -> AvailabilityResponse:
    """
    POST counterpart for availability checks when geometry payload is too large for GET query strings.
    """
    try:
        res = check_dataset_availability(
            dataset_id=dataset_id,
            geometry=req.geometry,
            bbox=req.bbox,
            start=req.start,
            end=req.end,
        )
        return AvailabilityResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e).lower() else 400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Availability check failed: {e}")
