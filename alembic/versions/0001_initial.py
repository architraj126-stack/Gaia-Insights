"""Initial schema: variables, dataset_products, dataset_fields, regions,
analysis_runs, analysis_outputs, reports, jobs, provenance_events.

Revision ID: 0001
Revises: 
Create Date: 2026-11-13
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Multi-dialect JSON type: uses native JSONB on PostgreSQL, standard JSON elsewhere
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # variables
    # -----------------------------------------------------------------------
    op.create_table(
        "variables",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("scientific_question", sa.Text, nullable=False),
        sa.Column("default_dataset_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="Available"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # -----------------------------------------------------------------------
    # dataset_products
    # -----------------------------------------------------------------------
    op.create_table(
        "dataset_products",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "variable_id",
            sa.String(64),
            sa.ForeignKey("variables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_name", sa.String(512), nullable=False),
        sa.Column("provider", sa.String(255), nullable=False),
        sa.Column("short_name", sa.String(128), nullable=False),
        sa.Column("collection_id", sa.String(128), nullable=True),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("doi", sa.String(512), nullable=True),
        sa.Column("doi_status", sa.String(64), nullable=False, server_default="Needs validation"),
        sa.Column("native_variable_name", sa.String(64), nullable=False),
        sa.Column("long_name", sa.String(512), nullable=False),
        sa.Column("var_desc", sa.String(512), nullable=True),
        sa.Column("units", sa.String(64), nullable=False),
        sa.Column("displayed_unit_conversion", sa.String(255), nullable=True),
        sa.Column("valid_range_min", sa.Float, nullable=True),
        sa.Column("valid_range_max", sa.Float, nullable=True),
        sa.Column("fill_value", sa.Float, nullable=True),
        sa.Column("spatial_grid", sa.String(64), nullable=False),
        sa.Column("crs", sa.String(64), nullable=False, server_default="EPSG:4326"),
        sa.Column("cell_dim_x", sa.Float, nullable=True),
        sa.Column("cell_dim_y", sa.Float, nullable=True),
        sa.Column("spatial_coverage", sa.String(512), nullable=False),
        sa.Column("spatial_resolution", sa.String(64), nullable=False),
        sa.Column("temporal_resolution", sa.String(64), nullable=False),
        sa.Column("start_date", sa.String(32), nullable=False),
        sa.Column("latest_observation_date", sa.Date, nullable=True),
        sa.Column("last_catalogue_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("update_latency", sa.String(255), nullable=True),
        sa.Column(
            "update_latency_status",
            sa.String(64),
            nullable=False,
            server_default="Needs validation",
        ),
        sa.Column("product_documentation", sa.String(1024), nullable=True),
        sa.Column("citation", sa.Text, nullable=True),
        sa.Column("access_url", sa.String(1024), nullable=True),
        sa.Column("opendap_url", sa.String(1024), nullable=True),
        sa.Column("terms_licensing", sa.Text, nullable=True),
        sa.Column("known_limitations", sa.Text, nullable=True),
        sa.Column("no_data_mask_semantics", sa.Text, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="Available"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_dataset_products_variable_id", "dataset_products", ["variable_id"])

    # -----------------------------------------------------------------------
    # dataset_fields
    # -----------------------------------------------------------------------
    op.create_table(
        "dataset_fields",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "dataset_id",
            sa.String(128),
            sa.ForeignKey("dataset_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_short_name", sa.String(64), nullable=False),
        sa.Column("long_name", sa.String(512), nullable=False),
        sa.Column("units", sa.String(64), nullable=False),
        sa.Column("vertical_level", sa.String(64), nullable=True),
        sa.Column("fill_value", sa.Float, nullable=True),
        sa.Column("aggregation_semantics", sa.String(255), nullable=True),
        sa.UniqueConstraint("dataset_id", "field_short_name", name="uq_dataset_field"),
    )
    op.create_index("ix_dataset_fields_dataset_id", "dataset_fields", ["dataset_id"])

    # -----------------------------------------------------------------------
    # regions
    # -----------------------------------------------------------------------
    op.create_table(
        "regions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("name", sa.String(512), nullable=True),
        sa.Column("geometry_type", sa.String(32), nullable=True),
        sa.Column("geometry", JSON_TYPE, nullable=True),
        sa.Column("crs", sa.String(64), nullable=False, server_default="EPSG:4326"),
        sa.Column("area_km2", sa.Float, nullable=True),
        sa.Column("bbox", JSON_TYPE, nullable=True),
        sa.Column("centroid", JSON_TYPE, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_regions_session_id", "regions", ["session_id"])

    # -----------------------------------------------------------------------
    # analysis_runs
    # -----------------------------------------------------------------------
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("run_type", sa.String(64), nullable=False),
        sa.Column(
            "dataset_id",
            sa.String(128),
            sa.ForeignKey("dataset_products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("dataset_version", sa.String(64), nullable=True),
        sa.Column("request_params", JSON_TYPE, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("warnings", JSON_TYPE, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_analysis_runs_session_id", "analysis_runs", ["session_id"])

    # -----------------------------------------------------------------------
    # analysis_outputs
    # -----------------------------------------------------------------------
    op.create_table(
        "analysis_outputs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(64),
            sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("output_type", sa.String(64), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("summary", JSON_TYPE, nullable=True),
        sa.Column("provenance", JSON_TYPE, nullable=True),
        sa.Column("output_units", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_analysis_outputs_run_id", "analysis_outputs", ["run_id"])

    # -----------------------------------------------------------------------
    # reports
    # -----------------------------------------------------------------------
    op.create_table(
        "reports",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("selected_analysis_ids", JSON_TYPE, nullable=True),
        sa.Column("chosen_sections", JSON_TYPE, nullable=True),
        sa.Column("export_format", sa.String(16), nullable=True),
        sa.Column("output_path", sa.String(1024), nullable=True),
        sa.Column("citation_snapshot", JSON_TYPE, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reports_session_id", "reports", ["session_id"])

    # -----------------------------------------------------------------------
    # jobs
    # -----------------------------------------------------------------------
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("percent_complete", sa.Float, nullable=True),
        sa.Column("messages", JSON_TYPE, nullable=True),
        sa.Column("result_url", sa.String(1024), nullable=True),
        sa.Column("request_params", JSON_TYPE, nullable=True),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -----------------------------------------------------------------------
    # provenance_events
    # -----------------------------------------------------------------------
    op.create_table(
        "provenance_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.String(128),
            sa.ForeignKey("dataset_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("old_version", sa.String(64), nullable=True),
        sa.Column("new_version", sa.String(64), nullable=True),
        sa.Column("old_latest_observation_date", sa.Date, nullable=True),
        sa.Column("new_latest_observation_date", sa.Date, nullable=True),
        sa.Column("detail", JSON_TYPE, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_provenance_events_dataset_id", "provenance_events", ["dataset_id"])


def downgrade() -> None:
    op.drop_table("provenance_events")
    op.drop_table("jobs")
    op.drop_table("reports")
    op.drop_table("analysis_outputs")
    op.drop_table("analysis_runs")
    op.drop_table("regions")
    op.drop_table("dataset_fields")
    op.drop_table("dataset_products")
    op.drop_table("variables")
