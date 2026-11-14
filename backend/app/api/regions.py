import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.services.boundaries import get_boundary_by_id, search_boundaries
from backend.app.services.geometry import validate_and_normalize_geometry

router = APIRouter(prefix="/api/regions", tags=["Regions"])


class RegionValidateRequest(BaseModel):
    geometry: Optional[Dict[str, Any]] = Field(None, description="GeoJSON geometry or Feature")
    crs: str = Field("EPSG:4326", description="Coordinate Reference System of input coordinates")
    point: Optional[List[float]] = Field(None, description="[lon, lat] coordinates for point buffer mode")
    radius_km: Optional[float] = Field(None, description="Buffer radius in kilometers")
    radius_m: Optional[float] = Field(None, description="Buffer radius in meters")
    label: Optional[str] = Field(None, description="Human readable label for the region")
    type: Optional[str] = Field(None, description="Region type (admin, polygon, rectangle, point_buffer)")


class RegionValidateResponse(BaseModel):
    status: str
    crs: str
    geometry: Dict[str, Any]
    area_km2: float
    bbox: List[float]
    centroid: List[float]
    warnings: List[str]


@router.get("/search")
async def search_regions_endpoint(
    q: str = Query("", description="Place name, country, state, or ISO code query"),
    limit: int = Query(25, ge=1, le=100, description="Maximum number of search results to return"),
) -> List[Dict[str, Any]]:
    """
    Search administrative boundaries (countries, states, provinces) from Natural Earth.
    """
    return search_boundaries(query=q, limit=limit)


@router.get("/{region_id}/geometry")
async def get_region_geometry_endpoint(region_id: str) -> Dict[str, Any]:
    """
    Retrieve full GeoJSON geometry and bounding box for a specific administrative boundary ID.
    """
    region = get_boundary_by_id(region_id)
    if not region:
        raise HTTPException(status_code=404, detail=f"Region boundary '{region_id}' not found.")
    return region


@router.post("/validate", response_model=RegionValidateResponse)
async def validate_region_endpoint(req: RegionValidateRequest) -> RegionValidateResponse:
    """
    Validates, repairs (make_valid), normalizes antimeridian crossings and longitudes,
    and computes geodesic area (via pyproj), bbox, and centroid for an input GeoJSON geometry
    or point + radius buffer.
    """
    try:
        res = validate_and_normalize_geometry(
            geometry=req.geometry,
            crs=req.crs,
            point=req.point,
            radius_km=req.radius_km,
            radius_m=req.radius_m,
        )
        return RegionValidateResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {e}")
