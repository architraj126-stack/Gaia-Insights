"""
Catalog API endpoints — Phase 3a.

Returns variables and dataset products from the PostgreSQL database.
If the database is unavailable, falls back to the YAML seed files so the
API never crashes due to a missing DB connection.

Endpoints:
  GET /api/catalog/variables
  GET /api/catalog/datasets?variable={id}
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.db.models import DatasetProduct as DBDatasetProduct
from backend.app.db.models import Variable as DBVariable
from backend.app.db.session import AsyncSessionLocal

logger = logging.getLogger("backend.api.catalog")
router = APIRouter(prefix="/api/catalog", tags=["Catalog"])

SEED_DIR = Path(__file__).resolve().parent.parent.parent / "catalog" / "seed"


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class DatasetModel(BaseModel):
    id: str
    variable_id: str
    product_name: str
    provider: str
    short_name: str
    collection_id: Optional[str] = None
    version: str
    doi: Optional[str] = None
    doi_status: str = "Needs validation"
    native_variable_name: str
    long_name: str
    var_desc: Optional[str] = None
    units: str
    displayed_unit_conversion: Optional[str] = None
    valid_range: Optional[List[float]] = None
    fill_value: Optional[float] = None
    spatial_grid: str
    crs: str
    cell_dimensions: Optional[List[float]] = None
    spatial_coverage: str
    spatial_resolution: str
    temporal_resolution: str
    start_date: str
    # Phase 3a: real values from DB (None only when genuinely unknown)
    latest_observation_date: Optional[str] = None
    # Separate "last checked" timestamp per SPEC 15.3
    last_catalogue_check: Optional[str] = None
    update_latency: Optional[str] = None
    update_latency_status: str = "Needs validation"
    product_documentation: Optional[str] = None
    citation: Optional[str] = None
    access_url: Optional[str] = None
    opendap_url: Optional[str] = None
    terms_licensing: Optional[str] = None
    known_limitations: Optional[str] = None
    no_data_mask_semantics: Optional[str] = None
    status: str = "Available"


class VariableModel(BaseModel):
    id: str
    name: str
    category: str
    description: str
    scientific_question: str
    default_dataset_id: str
    status: str = "Available"
    datasets: List[DatasetModel] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# DB-backed loader
# ---------------------------------------------------------------------------


def _db_dataset_to_model(ds: DBDatasetProduct) -> DatasetModel:
    """Convert a DatasetProduct ORM object to a Pydantic DatasetModel."""
    valid_range: Optional[List[float]] = None
    if ds.valid_range_min is not None and ds.valid_range_max is not None:
        valid_range = [ds.valid_range_min, ds.valid_range_max]

    cell_dims: Optional[List[float]] = None
    if ds.cell_dim_x is not None and ds.cell_dim_y is not None:
        cell_dims = [ds.cell_dim_x, ds.cell_dim_y]

    return DatasetModel(
        id=ds.id,
        variable_id=ds.variable_id,
        product_name=ds.product_name,
        provider=ds.provider,
        short_name=ds.short_name,
        collection_id=ds.collection_id,
        version=ds.version,
        doi=ds.doi,
        doi_status=ds.doi_status,
        native_variable_name=ds.native_variable_name,
        long_name=ds.long_name,
        var_desc=ds.var_desc,
        units=ds.units,
        displayed_unit_conversion=ds.displayed_unit_conversion,
        valid_range=valid_range,
        fill_value=ds.fill_value,
        spatial_grid=ds.spatial_grid,
        crs=ds.crs,
        cell_dimensions=cell_dims,
        spatial_coverage=ds.spatial_coverage,
        spatial_resolution=ds.spatial_resolution,
        temporal_resolution=ds.temporal_resolution,
        start_date=ds.start_date,
        # SPEC 15.3: return date as ISO string "YYYY-MM-DD", or None if not yet checked
        latest_observation_date=(
            ds.latest_observation_date.isoformat() if ds.latest_observation_date else None
        ),
        last_catalogue_check=(
            ds.last_catalogue_check.isoformat() if ds.last_catalogue_check else None
        ),
        update_latency=ds.update_latency,
        update_latency_status=ds.update_latency_status,
        product_documentation=ds.product_documentation,
        citation=ds.citation,
        access_url=ds.access_url,
        opendap_url=ds.opendap_url,
        terms_licensing=ds.terms_licensing,
        known_limitations=ds.known_limitations,
        no_data_mask_semantics=ds.no_data_mask_semantics,
        status=ds.status,
    )


async def _load_catalog_from_db() -> List[VariableModel]:
    """Load variables + datasets from PostgreSQL. Raises on DB failure."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DBVariable)
            .options(selectinload(DBVariable.dataset_products))
            .order_by(DBVariable.id)
        )
        db_variables = result.scalars().all()

    out: List[VariableModel] = []
    for v in db_variables:
        datasets = [_db_dataset_to_model(ds) for ds in v.dataset_products]
        out.append(
            VariableModel(
                id=v.id,
                name=v.name,
                category=v.category,
                description=v.description,
                scientific_question=v.scientific_question,
                default_dataset_id=v.default_dataset_id or "",
                status=v.status,
                datasets=datasets,
            )
        )
    out.sort(key=lambda x: (0 if x.id == "precipitation" else 1, x.id))
    return out


# ---------------------------------------------------------------------------
# YAML fallback loader (used when DB is unavailable)
# ---------------------------------------------------------------------------


def load_catalog_seed() -> List[VariableModel]:
    """
    Load catalog from seed YAML files.
    Used as a fallback when the database is not available.
    NOTE: This returns latest_observation_date=None (not yet checked from DB).
    """
    if not SEED_DIR.exists():
        return []

    variables: List[VariableModel] = []
    for yaml_path in sorted(SEED_DIR.glob("*.yaml")):
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            continue

        datasets: List[DatasetModel] = []
        for ds_raw in data.get("datasets", []):
            vr = ds_raw.get("valid_range")
            cd = ds_raw.get("cell_dimensions")
            datasets.append(
                DatasetModel(
                    id=ds_raw["id"],
                    variable_id=ds_raw["variable_id"],
                    product_name=ds_raw["product_name"],
                    provider=ds_raw["provider"],
                    short_name=ds_raw["short_name"],
                    collection_id=ds_raw.get("collection_id"),
                    version=ds_raw.get("version", ""),
                    doi=ds_raw.get("doi"),
                    doi_status=ds_raw.get("doi_status", "Needs validation"),
                    native_variable_name=ds_raw["native_variable_name"],
                    long_name=ds_raw["long_name"],
                    var_desc=ds_raw.get("var_desc"),
                    units=ds_raw["units"],
                    displayed_unit_conversion=ds_raw.get("displayed_unit_conversion"),
                    valid_range=vr,
                    fill_value=ds_raw.get("fill_value"),
                    spatial_grid=ds_raw["spatial_grid"],
                    crs=ds_raw.get("crs", "EPSG:4326"),
                    cell_dimensions=cd,
                    spatial_coverage=ds_raw["spatial_coverage"],
                    spatial_resolution=ds_raw["spatial_resolution"],
                    temporal_resolution=ds_raw["temporal_resolution"],
                    start_date=ds_raw["start_date"],
                    latest_observation_date=ds_raw.get("latest_observation_date"),
                    last_catalogue_check=None,
                    update_latency=ds_raw.get("update_latency"),
                    update_latency_status=ds_raw.get("update_latency_status", "Needs validation"),
                    product_documentation=ds_raw.get("product_documentation"),
                    citation=ds_raw.get("citation"),
                    access_url=ds_raw.get("access_url"),
                    opendap_url=ds_raw.get("opendap_url"),
                    terms_licensing=ds_raw.get("terms_licensing"),
                    known_limitations=ds_raw.get("known_limitations"),
                    no_data_mask_semantics=ds_raw.get("no_data_mask_semantics"),
                    status=ds_raw.get("status", "Available"),
                )
            )

        variables.append(
            VariableModel(
                id=data["id"],
                name=data["name"],
                category=data["category"],
                description=data["description"],
                scientific_question=data.get("scientific_question", ""),
                default_dataset_id=data.get("default_dataset_id", ""),
                status=data.get("status", "Available"),
                datasets=datasets,
            )
        )
    variables.sort(key=lambda x: (0 if x.id == "precipitation" else 1, x.id))
    return variables


async def _load_catalog_with_fallback() -> List[VariableModel]:
    """Try DB first; fall back to YAML seed if DB is unavailable."""
    try:
        return await _load_catalog_from_db()
    except Exception as exc:
        logger.warning(
            "Database unavailable (%s); serving catalog from YAML seed files.", exc
        )
        seed_vars = load_catalog_seed()
        # SPEC 3.2 / Requirement 6: When the database is offline and the catalogue falls back
        # to the YAML seed, mark datasets "Needs validation" (unless uningested)
        for v in seed_vars:
            if not v.status.startswith("Unavailable"):
                v.status = "Needs validation"
            for ds in v.datasets:
                if not ds.status.startswith("Unavailable"):
                    ds.status = "Needs validation"
        return seed_vars


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/variables", response_model=List[VariableModel])
async def get_catalog_variables() -> List[VariableModel]:
    """
    Returns configured variables and their dataset choices.
    Served from PostgreSQL; falls back to YAML seed when DB is unavailable.
    """
    return await _load_catalog_with_fallback()


@router.get("/datasets", response_model=List[DatasetModel])
async def get_catalog_datasets(
    variable: Optional[str] = Query(None, description="Optional variable ID to filter datasets")
) -> List[DatasetModel]:
    """
    Returns dataset products matching the optional variable ID filter.
    Served from PostgreSQL; falls back to YAML seed when DB is unavailable.
    """
    variables = await _load_catalog_with_fallback()
    matching: List[DatasetModel] = []
    for v in variables:
        if variable is None or v.id == variable:
            matching.extend(v.datasets)
    return matching
