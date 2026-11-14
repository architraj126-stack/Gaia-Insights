"""
Report Generation Endpoints (SPEC 10.7, 10.8, 15.4, 17.3).
Provides endpoints to synthesize and export reports (PDF, CSV, PNG, GeoTIFF)
across Page 3 (Trends), Page 4 (Change Detection), and Page 5 (Significance).
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Job, Report
from backend.app.api.analysis import get_db_session
from backend.app.services.change import OUTPUTS_DIR
from backend.app.services.reports import create_report

logger = logging.getLogger("backend.api.reports")

router = APIRouter(tags=["reports"])


class CreateReportRequest(BaseModel):
    title: Optional[str] = "Earth Science Explorer — Scientific Analysis Report"
    series_id: Optional[str] = None
    change_run_id: Optional[str] = None
    significance_run_id: Optional[str] = None
    sections: Optional[Dict[str, bool]] = None


@router.post("/api/reports", status_code=status.HTTP_201_CREATED)
async def generate_report_endpoint(
    req: CreateReportRequest,
    session: Optional[AsyncSession] = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    Assembles and exports a unified scientific report (SPEC 10.7, 10.8).
    Enforces strict consistency: refuses to combine runs with conflicting versions,
    regions, or dates.
    """
    try:
        report_data = create_report(
            series_id=req.series_id,
            change_run_id=req.change_run_id,
            significance_run_id=req.significance_run_id,
            title=req.title,
            sections=req.sections,
            output_dir=OUTPUTS_DIR,
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as exc:
        logger.error("Failed to generate report: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report assembly failed: {exc}",
        )

    # Persist in DB if session is active
    if session:
        try:
            report_id = report_data["report_id"]
            db_report = Report(
                id=report_id,
                session_id=None,
                selected_analysis_ids=[req.series_id, req.change_run_id, req.significance_run_id],
                chosen_sections=report_data.get("sections_enabled"),
                export_format="pdf",
                output_path=str(OUTPUTS_DIR / f"report_{report_id}.pdf"),
                citation_snapshot=report_data.get("dataset_info"),
                status="completed",
                completed_at=datetime.now(timezone.utc),
            )
            session.add(db_report)
            await session.commit()
        except Exception as e:
            logger.warning("Failed to record Report in DB: %s", e)

    return report_data


@router.get("/api/reports/{report_id}")
async def get_report_endpoint(report_id: str) -> Dict[str, Any]:
    """Retrieves metadata and live preview payload for a generated report."""
    res_file = OUTPUTS_DIR / f"report_{report_id}.json"
    if res_file.exists():
        with open(res_file, "r", encoding="utf-8") as f:
            return json.load(f)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Report '{report_id}' not found.",
    )


@router.get("/api/reports/{report_id}/pdf")
async def download_report_pdf(report_id: str) -> FileResponse:
    """Downloads the compiled ReportLab PDF."""
    pdf_file = OUTPUTS_DIR / f"report_{report_id}.pdf"
    if pdf_file.exists():
        return FileResponse(
            path=str(pdf_file),
            media_type="application/pdf",
            filename=f"earth_science_report_{report_id}.pdf",
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"PDF for report '{report_id}' not found.",
    )


@router.get("/api/reports/{report_id}/csv")
async def download_report_csv(report_id: str) -> FileResponse:
    """Downloads the structured CSV export."""
    csv_file = OUTPUTS_DIR / f"report_{report_id}_timeseries.csv"
    if csv_file.exists():
        return FileResponse(
            path=str(csv_file),
            media_type="text/csv",
            filename=f"earth_science_timeseries_{report_id}.csv",
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"CSV for report '{report_id}' not found.",
    )


@router.get("/api/reports/{report_id}/chart.png")
async def get_report_chart_png(report_id: str) -> FileResponse:
    """Serves the rendered high-resolution time series chart PNG."""
    png_file = OUTPUTS_DIR / f"report_{report_id}_chart.png"
    if png_file.exists():
        return FileResponse(
            path=str(png_file),
            media_type="image/png",
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Chart PNG for report '{report_id}' not found.",
    )
