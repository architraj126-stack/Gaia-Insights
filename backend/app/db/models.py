"""
SQLAlchemy ORM models for the Earth Science Explorer (Phase 3a).

Tables (per SPEC 13.2):
  - variables
  - dataset_products
  - dataset_fields
  - regions
  - analysis_runs
  - analysis_outputs
  - reports
  - jobs
  - provenance_events  (version-change audit log; never overwrite history)
"""
from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Variable
# ---------------------------------------------------------------------------

class Variable(Base):
    """App-level variable (Precipitation, LST, SST, etc.)."""

    __tablename__ = "variables"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    scientific_question: Mapped[str] = mapped_column(Text, nullable=False)
    default_dataset_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Available")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # relationships
    dataset_products: Mapped[list[DatasetProduct]] = relationship(
        "DatasetProduct", back_populates="variable", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# DatasetProduct  (SPEC 6.2 — every field listed there must live here)
# ---------------------------------------------------------------------------

class DatasetProduct(Base):
    """
    A specific, pinned dataset product version (e.g. GPCP V2.3 monthly).

    Stores every field required by SPEC 6.2.
    """

    __tablename__ = "dataset_products"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    variable_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("variables.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # --- SPEC 6.2: human-readable product name, provider, short name ---
    product_name: Mapped[str] = mapped_column(String(512), nullable=False)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str] = mapped_column(String(128), nullable=False)
    collection_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # --- SPEC 6.2: version / DOI / persistent identifier ---
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    doi: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    doi_status: Mapped[str] = mapped_column(String(64), nullable=False, default="Needs validation")

    # --- SPEC 6.2: native variable short name, long name, units, valid range, fill value ---
    native_variable_name: Mapped[str] = mapped_column(String(64), nullable=False)
    long_name: Mapped[str] = mapped_column(String(512), nullable=False)
    var_desc: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    units: Mapped[str] = mapped_column(String(64), nullable=False)
    displayed_unit_conversion: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    valid_range_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    valid_range_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fill_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # --- SPEC 6.2: native spatial grid, CRS, cell dimensions, spatial coverage ---
    spatial_grid: Mapped[str] = mapped_column(String(64), nullable=False)
    crs: Mapped[str] = mapped_column(String(64), nullable=False, default="EPSG:4326")
    cell_dim_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cell_dim_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spatial_coverage: Mapped[str] = mapped_column(String(512), nullable=False)
    spatial_resolution: Mapped[str] = mapped_column(String(64), nullable=False)

    # --- SPEC 6.2: temporal resolution, start date, latest observation, update latency ---
    temporal_resolution: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[str] = mapped_column(String(32), nullable=False)  # ISO 8601 string

    # SPEC 15.3: two separate timestamps
    latest_observation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_catalogue_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    update_latency: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    update_latency_status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Needs validation"
    )

    # --- SPEC 6.2: product documentation, citation, access URL, licence ---
    product_documentation: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    citation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    opendap_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    terms_licensing: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- SPEC 6.2: known limitations, no-data semantics ---
    known_limitations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    no_data_mask_semantics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Available")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # relationships
    variable: Mapped[Variable] = relationship("Variable", back_populates="dataset_products")
    fields: Mapped[list[DatasetField]] = relationship(
        "DatasetField", back_populates="dataset_product", cascade="all, delete-orphan"
    )
    provenance_events: Mapped[list[ProvenanceEvent]] = relationship(
        "ProvenanceEvent", back_populates="dataset_product"
    )


# ---------------------------------------------------------------------------
# DatasetField  (SPEC 13.2)
# ---------------------------------------------------------------------------

class DatasetField(Base):
    """A specific variable field within a DatasetProduct (e.g. precip, QV2M)."""

    __tablename__ = "dataset_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("dataset_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_short_name: Mapped[str] = mapped_column(String(64), nullable=False)
    long_name: Mapped[str] = mapped_column(String(512), nullable=False)
    units: Mapped[str] = mapped_column(String(64), nullable=False)
    vertical_level: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    fill_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    aggregation_semantics: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("dataset_id", "field_short_name", name="uq_dataset_field"),)

    dataset_product: Mapped[DatasetProduct] = relationship("DatasetProduct", back_populates="fields")


# ---------------------------------------------------------------------------
# Region  (SPEC 13.2)
# ---------------------------------------------------------------------------

class Region(Base):
    """User/session-selected study region."""

    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    geometry_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    geometry: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    crs: Mapped[str] = mapped_column(String(64), nullable=False, default="EPSG:4326")
    area_km2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    centroid: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# AnalysisRun  (SPEC 13.2)
# ---------------------------------------------------------------------------

class AnalysisRun(Base):
    """Record of a single analysis invocation."""

    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    run_type: Mapped[str] = mapped_column(String(64), nullable=False)  # timeseries|change_map|significance
    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(128), ForeignKey("dataset_products.id", ondelete="SET NULL"), nullable=True
    )
    dataset_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    request_params: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    warnings: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    outputs: Mapped[list[AnalysisOutput]] = relationship(
        "AnalysisOutput", back_populates="run", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# AnalysisOutput  (SPEC 13.2)
# ---------------------------------------------------------------------------

class AnalysisOutput(Base):
    """Output artefacts from an AnalysisRun."""

    __tablename__ = "analysis_outputs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    output_type: Mapped[str] = mapped_column(String(64), nullable=False)  # series|raster|table
    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    summary: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    provenance: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    output_units: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[AnalysisRun] = relationship("AnalysisRun", back_populates="outputs")


# ---------------------------------------------------------------------------
# Report  (SPEC 13.2)
# ---------------------------------------------------------------------------

class Report(Base):
    """A generated report combining outputs from multiple analysis runs."""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    selected_analysis_ids: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    chosen_sections: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    export_format: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    output_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    citation_snapshot: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# Job  (async task tracking — SPEC 12.4)
# ---------------------------------------------------------------------------

class Job(Base):
    """Background job tracking entry (supports long-running analysis)."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    percent_complete: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    messages: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    result_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    request_params: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# ProvenanceEvent  (SPEC 6.4 — dataset version change audit log)
# ---------------------------------------------------------------------------

class ProvenanceEvent(Base):
    """
    Immutable audit log row created whenever a DatasetProduct version changes.
    Never overwrite; always INSERT a new row (SPEC 6.4).
    """

    __tablename__ = "provenance_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    dataset_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("dataset_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)  # version_change|refresh|seed
    old_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    new_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    old_latest_observation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    new_latest_observation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    detail: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dataset_product: Mapped[DatasetProduct] = relationship(
        "DatasetProduct", back_populates="provenance_events"
    )
