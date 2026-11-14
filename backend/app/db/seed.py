"""
Idempotent database seeder.

Reads all YAML files from backend/catalog/seed/*.yaml and upserts them into
the database. Safe to call multiple times (startup idempotency).

Version-change guard: if a DatasetProduct already exists in the DB with a
DIFFERENT version string, we:
  1. Write a ProvenanceEvent row (event_type='version_change') — never overwrite.
  2. Update the product row to the new version.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import (
    DatasetField,
    DatasetProduct,
    ProvenanceEvent,
    Variable,
)

logger = logging.getLogger("backend.db.seed")

SEED_DIR = Path(__file__).resolve().parent.parent.parent / "catalog" / "seed"


def _extract_valid_range(raw: Optional[List[float]]) -> tuple[Optional[float], Optional[float]]:
    if raw and len(raw) == 2:
        return float(raw[0]), float(raw[1])
    return None, None


def _extract_cell_dims(raw: Optional[List[float]]) -> tuple[Optional[float], Optional[float]]:
    if raw and len(raw) >= 2:
        return float(raw[0]), float(raw[1])
    if raw and len(raw) == 1:
        return float(raw[0]), float(raw[0])
    return None, None


async def seed_catalog(session: AsyncSession) -> None:
    """
    Load every seed YAML file and upsert variables + dataset products into
    the database. Version changes create a ProvenanceEvent instead of
    silently overwriting history (SPEC 6.4).
    """
    if not SEED_DIR.exists():
        logger.warning("Seed directory not found: %s", SEED_DIR)
        return

    yaml_files = sorted(SEED_DIR.glob("*.yaml"))
    if not yaml_files:
        logger.warning("No seed YAML files found in %s", SEED_DIR)
        return

    for yaml_path in yaml_files:
        logger.info("Seeding from %s", yaml_path.name)
        with open(yaml_path, "r", encoding="utf-8") as fh:
            data: Dict[str, Any] = yaml.safe_load(fh)
        if not data:
            continue
        await _upsert_variable(session, data)

    logger.info("Catalog seed completed.")


async def _upsert_variable(session: AsyncSession, data: Dict[str, Any]) -> None:
    var_id: str = data["id"]

    # Fetch or create Variable
    result = await session.execute(select(Variable).where(Variable.id == var_id))
    variable: Optional[Variable] = result.scalar_one_or_none()

    if variable is None:
        variable = Variable(
            id=var_id,
            name=data["name"],
            category=data["category"],
            description=data["description"],
            scientific_question=data.get("scientific_question", ""),
            default_dataset_id=data.get("default_dataset_id"),
            status=data.get("status", "Available"),
        )
        session.add(variable)
        logger.info("Inserted Variable: %s", var_id)
    else:
        # Update mutable fields
        variable.name = data["name"]
        variable.category = data["category"]
        variable.description = data["description"]
        variable.scientific_question = data.get("scientific_question", variable.scientific_question)
        variable.default_dataset_id = data.get("default_dataset_id", variable.default_dataset_id)
        variable.status = data.get("status", variable.status)
        logger.debug("Updated Variable: %s", var_id)

    for ds_data in data.get("datasets", []):
        await _upsert_dataset_product(session, ds_data)


async def _upsert_dataset_product(session: AsyncSession, ds: Dict[str, Any]) -> None:
    ds_id: str = ds["id"]
    new_version: str = ds.get("version", "")

    result = await session.execute(
        select(DatasetProduct).where(DatasetProduct.id == ds_id)
    )
    existing: Optional[DatasetProduct] = result.scalar_one_or_none()

    vr_min, vr_max = _extract_valid_range(ds.get("valid_range"))
    cd_x, cd_y = _extract_cell_dims(ds.get("cell_dimensions"))

    if existing is None:
        # First-time insert
        product = DatasetProduct(
            id=ds_id,
            variable_id=ds["variable_id"],
            product_name=ds["product_name"],
            provider=ds["provider"],
            short_name=ds["short_name"],
            collection_id=ds.get("collection_id"),
            version=new_version,
            doi=ds.get("doi"),
            doi_status=ds.get("doi_status", "Needs validation"),
            native_variable_name=ds["native_variable_name"],
            long_name=ds["long_name"],
            var_desc=ds.get("var_desc"),
            units=ds["units"],
            displayed_unit_conversion=ds.get("displayed_unit_conversion"),
            valid_range_min=vr_min,
            valid_range_max=vr_max,
            fill_value=ds.get("fill_value"),
            spatial_grid=ds["spatial_grid"],
            crs=ds.get("crs", "EPSG:4326"),
            cell_dim_x=cd_x,
            cell_dim_y=cd_y,
            spatial_coverage=ds["spatial_coverage"],
            spatial_resolution=ds["spatial_resolution"],
            temporal_resolution=ds["temporal_resolution"],
            start_date=ds["start_date"],
            # latest_observation_date and last_catalogue_check intentionally left None;
            # they are populated by catalogue_refresh, not from seed YAML (SPEC 6.3).
            latest_observation_date=None,
            last_catalogue_check=None,
            update_latency=ds.get("update_latency"),
            update_latency_status=ds.get("update_latency_status", "Needs validation"),
            product_documentation=ds.get("product_documentation"),
            citation=ds.get("citation"),
            access_url=ds.get("access_url"),
            opendap_url=ds.get("opendap_url"),
            terms_licensing=ds.get("terms_licensing"),
            known_limitations=ds.get("known_limitations"),
            no_data_mask_semantics=ds.get("no_data_mask_semantics"),
            status=ds.get("status", "Available"),
        )
        session.add(product)
        # Emit seed provenance event
        session.add(
            ProvenanceEvent(
                dataset_id=ds_id,
                event_type="seed",
                new_version=new_version,
                detail={"message": "Initial seed from YAML"},
            )
        )
        logger.info("Inserted DatasetProduct: %s (version %s)", ds_id, new_version)

    else:
        # Detect version change — SPEC 6.4: create a provenance event, never silently overwrite
        if existing.version != new_version:
            logger.info(
                "Version change detected for %s: %s → %s",
                ds_id,
                existing.version,
                new_version,
            )
            session.add(
                ProvenanceEvent(
                    dataset_id=ds_id,
                    event_type="version_change",
                    old_version=existing.version,
                    new_version=new_version,
                    old_latest_observation_date=existing.latest_observation_date,
                    detail={
                        "message": f"Version changed from {existing.version!r} to {new_version!r} during seed"
                    },
                )
            )

        # Update all scalar fields that might change between seed runs
        existing.version = new_version
        existing.product_name = ds["product_name"]
        existing.provider = ds["provider"]
        existing.short_name = ds["short_name"]
        existing.collection_id = ds.get("collection_id", existing.collection_id)
        existing.doi = ds.get("doi", existing.doi)
        existing.doi_status = ds.get("doi_status", existing.doi_status)
        existing.native_variable_name = ds["native_variable_name"]
        existing.long_name = ds["long_name"]
        existing.var_desc = ds.get("var_desc", existing.var_desc)
        existing.units = ds["units"]
        existing.displayed_unit_conversion = ds.get("displayed_unit_conversion", existing.displayed_unit_conversion)
        existing.valid_range_min = vr_min if vr_min is not None else existing.valid_range_min
        existing.valid_range_max = vr_max if vr_max is not None else existing.valid_range_max
        existing.fill_value = ds.get("fill_value", existing.fill_value)
        existing.spatial_grid = ds["spatial_grid"]
        existing.crs = ds.get("crs", existing.crs)
        existing.cell_dim_x = cd_x if cd_x is not None else existing.cell_dim_x
        existing.cell_dim_y = cd_y if cd_y is not None else existing.cell_dim_y
        existing.spatial_coverage = ds["spatial_coverage"]
        existing.spatial_resolution = ds["spatial_resolution"]
        existing.temporal_resolution = ds["temporal_resolution"]
        existing.start_date = ds["start_date"]
        existing.update_latency = ds.get("update_latency", existing.update_latency)
        existing.update_latency_status = ds.get("update_latency_status", existing.update_latency_status)
        existing.product_documentation = ds.get("product_documentation", existing.product_documentation)
        existing.citation = ds.get("citation", existing.citation)
        existing.access_url = ds.get("access_url", existing.access_url)
        existing.opendap_url = ds.get("opendap_url", existing.opendap_url)
        existing.terms_licensing = ds.get("terms_licensing", existing.terms_licensing)
        existing.known_limitations = ds.get("known_limitations", existing.known_limitations)
        existing.no_data_mask_semantics = ds.get("no_data_mask_semantics", existing.no_data_mask_semantics)
        existing.status = ds.get("status", existing.status)
        logger.debug("Updated DatasetProduct: %s", ds_id)

    # Upsert DatasetField registry rows (SPEC 13.2, 14.3)
    fields = ds.get("fields")
    if not fields:
        fields = [{
            "field_short_name": ds["native_variable_name"],
            "long_name": ds["long_name"],
            "units": ds["units"],
            "vertical_level": "surface",
            "fill_value": ds.get("fill_value"),
            "aggregation_semantics": "rate_accumulate_by_month_days" if ds.get("units") == "mm/day" else "state_mean_time_weighted",
        }]
    for fld in fields:
        await _upsert_dataset_field(session, ds_id, fld)


async def _upsert_dataset_field(session: AsyncSession, dataset_id: str, fld_data: Dict[str, Any]) -> None:
    short_name = fld_data["field_short_name"]
    res = await session.execute(
        select(DatasetField).where(
            DatasetField.dataset_id == dataset_id,
            DatasetField.field_short_name == short_name,
        )
    )
    existing_field = res.scalar_one_or_none()
    if existing_field is None:
        new_fld = DatasetField(
            dataset_id=dataset_id,
            field_short_name=short_name,
            long_name=fld_data["long_name"],
            units=fld_data["units"],
            vertical_level=fld_data.get("vertical_level", "surface"),
            fill_value=fld_data.get("fill_value"),
            aggregation_semantics=fld_data.get("aggregation_semantics"),
        )
        session.add(new_fld)
        logger.info("Inserted DatasetField: %s.%s", dataset_id, short_name)
    else:
        existing_field.long_name = fld_data["long_name"]
        existing_field.units = fld_data["units"]
        existing_field.vertical_level = fld_data.get("vertical_level", existing_field.vertical_level)
        existing_field.fill_value = fld_data.get("fill_value", existing_field.fill_value)
        existing_field.aggregation_semantics = fld_data.get(
            "aggregation_semantics", existing_field.aggregation_semantics
        )
        logger.debug("Updated DatasetField: %s.%s", dataset_id, short_name)
