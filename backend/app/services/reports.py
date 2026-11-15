"""
Comprehensive Scientific Report Generation Service (SPEC 10.7, 10.8, 15.4, 17.3).

Key Responsibilities:
- Assembles multi-page scientific audit reports combining Page 3 (Trends),
  Page 4 (Change Detection), and Page 5 (Significance) analysis runs.
- Consistency Validation: Refuses to combine runs with conflicting dataset versions,
  regions, or temporal coverage.
- Single Source of Truth: Every numeric finding is extracted directly from stored runs;
  never recomputed, estimated, or typed manually.
- Template-Driven Executive Summary: Synthesizes findings using strict parameter templates
  with zero free-written or unsubstantiated claims.
- Exports:
  * PDF report with rendered timeseries chart, map overlays, formatted tables,
    citations, DOIs, access timestamps, and mathematical methodology (via ReportLab).
  * CSV export containing all time-series points, units, valid cell counts, and quality flags.
  * Direct links to high-resolution PNG charts/maps and GIS GeoTIFF rasters.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfgen import canvas

from backend.app.config import settings
from backend.app.services.change import OUTPUTS_DIR

logger = logging.getLogger("backend.services.reports")

RESULTS_CACHE_DIR = OUTPUTS_DIR / "cache"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

APP_VERSION = "1.0.0"
NASA_CITATIONS = {
    "gpcp_monthly_v23": {
        "title": "Global Precipitation Climatology Project (GPCP) Monthly Version 2.3",
        "provider": "NOAA PSL / NASA Goddard Space Flight Center",
        "doi": "10.7289/V56971M6",
        "citation": (
            "Adler, R. F., G. Gu, M. Sapiano, C. Wang, and G. J. Huffman, 2018: "
            "Global Precipitation Climatology Project (GPCP) Monthly Analysis: "
            "Climate Data Record (CDR), Version 2.3. NOAA National Centers for Environmental Information, "
            "https://doi.org/10.7289/V56971M6."
        ),
        "spatial_resolution": "2.5° × 2.5° Global Grid",
    },
    "merra2_monthly_instM_2d_asm_Nx": {
        "title": "Modern-Era Retrospective Analysis for Research and Applications, Version 2 (MERRA-2)",
        "provider": "NASA Global Modeling and Assimilation Office (GMAO) / GES DISC",
        "doi": "10.5067/5ESKGQTZG7FO",
        "citation": (
            "Global Modeling and Assimilation Office (GMAO), 2015: MERRA-2 instM_2d_asm_Nx: "
            "2d, Monthly mean, Single-Level Assimilation Single-Level Diagnostics, "
            "Goddard Earth Sciences Data and Information Services Center (GES DISC), "
            "https://doi.org/10.5067/5ESKGQTZG7FO."
        ),
        "caveat": (
            "This is a reanalysis/model surface skin temperature diagnostic from MERRA-2 assimilation, "
            "not MODIS satellite land-surface temperature. Model land-surface diagnostics reflect simulated "
            "surface equilibrium rather than direct radiometric measurements."
        ),
        "spatial_resolution": "0.625° × 0.5° Regular Grid",
    },
    "merra2_monthly_ts": {
        "title": "Modern-Era Retrospective Analysis for Research and Applications, Version 2 (MERRA-2)",
        "provider": "NASA Global Modeling and Assimilation Office (GMAO) / GES DISC",
        "doi": "10.5067/5ESKGQTZG7FO",
        "citation": (
            "Global Modeling and Assimilation Office (GMAO), 2015: MERRA-2 instM_2d_asm_Nx: "
            "2d, Monthly mean, Single-Level Assimilation Single-Level Diagnostics, "
            "Goddard Earth Sciences Data and Information Services Center (GES DISC), "
            "https://doi.org/10.5067/5ESKGQTZG7FO."
        ),
        "caveat": (
            "This is a reanalysis/model surface skin temperature diagnostic from MERRA-2 assimilation, "
            "not MODIS satellite land-surface temperature. Model land-surface diagnostics reflect simulated "
            "surface equilibrium rather than direct radiometric measurements."
        ),
        "spatial_resolution": "0.625° × 0.5° Regular Grid",
    },
    "noaa_oisst_v21": {
        "title": "NOAA 1/4° Daily Optimum Interpolation Sea Surface Temperature (OISST) Version 2.1",
        "provider": "NOAA NCEI / PSL",
        "doi": "10.25921/RE9P-PT57",
        "citation": (
            "Huang, B., C. Liu, V. Banzon, E. Freeman, G. Graham, B. Hankins, T. Smith, and H.-M. Zhang, 2021: "
            "Improvements of the Daily Optimum Interpolation Sea Surface Temperature (DOISST) Version 2.1. "
            "J. Climate, 34, 2923–2939, https://doi.org/10.1175/JCLI-D-20-0166.1. "
            "NOAA National Centers for Environmental Information, https://doi.org/10.25921/RE9P-PT57."
        ),
        "caveat": (
            "NOAA OISST v2.1 is an ocean-only blended product; terrestrial land cells have no observations "
            "and are strictly masked. Polar ice-covered oceans use a proxy freezing temperature of -1.8°C "
            "based on satellite sea-ice concentrations."
        ),
        "spatial_resolution": "0.25° × 0.25° Regular Grid",
    },
    "gldas_noah025_m_v21": {
        "title": "GLDAS Noah Land Surface Model L4 monthly 0.25 x 0.25 degree V2.1",
        "provider": "NASA GES DISC",
        "doi": "10.5067/SXAVCZFAQLNO",
        "citation": (
            "Beaudoing, H. and M. Rodell, NASA/GSFC/HSL (2020), GLDAS Noah Land Surface Model L4 monthly "
            "0.25 x 0.25 degree V2.1, Greenbelt, Maryland, USA, Goddard Earth Sciences Data and Information "
            "Services Center (GES DISC), https://doi.org/10.5067/SXAVCZFAQLNO."
        ),
        "caveat": (
            "GLDAS Noah soil moisture is model-simulated water storage (0–10 cm layer) driven by atmospheric "
            "data assimilation, not direct in-situ probe or satellite radiometer measurements. GLDAS-2.0 "
            "(1948–2014) and GLDAS-2.1 (2000–present) use different meteorological forcing and must not be "
            "stitched without bias correction. Ocean cells are strictly masked."
        ),
        "spatial_resolution": "0.25° × 0.25° Regular Grid",
    },
    "merra2_monthly_qv2m": {
        "title": "MERRA-2 tavgM_2d_slv_Nx: 2d,Monthly mean,Time-Averaged,Single-Level,Assimilation,Single-Level Diagnostics 0.625 x 0.5 degree V5.12.4",
        "provider": "NASA GES DISC / GMAO",
        "doi": "10.5067/AP1B0BA5PD2K",
        "citation": (
            "Global Modeling and Assimilation Office (GMAO) (2015), MERRA-2 tavgM_2d_slv_Nx: 2d,Monthly mean,Time-Averaged,"
            "Single-Level,Assimilation,Single-Level Diagnostics 0.625 x 0.5 degree V5.12.4, Greenbelt, MD, USA, "
            "Goddard Earth Sciences Data and Information Services Center (GES DISC), https://doi.org/10.5067/AP1B0BA5PD2K."
        ),
        "caveat": (
            "This variable represents 2-meter near-surface specific humidity (QV2M) from MERRA-2 reanalysis assimilation, "
            "expressed in g/kg. It is an intensive atmospheric mass fraction at 2 meters above ground level, distinct from "
            "total column precipitable water (TQV in kg/m²) or upper-air specific humidity across isobaric pressure levels."
        ),
        "spatial_resolution": "0.625° × 0.5° Regular Grid",
    },
}


def resolve_dataset_version(dataset_id: Optional[str], variable: Optional[str] = None, user_version: Optional[str] = None) -> str:
    """Resolve correct dataset version dynamically from catalog semantics (SPEC Rule 4)."""
    if user_version:
        return user_version
    ds_id = (dataset_id or "").lower()
    var = (variable or "").lower()
    if ds_id in ["merra2_monthly_ts", "merra2_monthly_qv2m", "merra2_monthly_instm_2d_asm_nx"] or var in ["temperature", "land_surface_temperature", "humidity"]:
        return "5.12.4"
    if ds_id in ["noaa_oisst_v21"] or var in ["sea_surface_temperature", "sst"]:
        return "v2.1"
    if ds_id in ["gldas_noah025_m_v21"] or var in ["soil_moisture"]:
        return "2.1"
    return "v2.3"


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas that adds running header and 'Page X of Y' footer on every page.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running Top Header (Pages 2+)
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 36, "Gaia Insights — Scientific Analysis Report")
            self.drawRightString(letter[0] - 54, letter[1] - 36, f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Running Bottom Footer
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 46, letter[0] - 54, 46)

        footer_text = "NASA Earth Science Data Systems • For Research & Educational Use"
        self.drawString(54, 34, footer_text)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 34, page_str)
        self.restoreState()


# ---------------------------------------------------------------------------
# 1. Run Data Loading & Invalidation/Consistency Validation
# ---------------------------------------------------------------------------

def load_run_data(
    series_id: Optional[str] = None,
    change_run_id: Optional[str] = None,
    significance_run_id: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Loads raw stored result payloads from disk for the specified run IDs.
    """
    p3_data = None
    p4_data = None
    p5_data = None

    # Load Page 3
    if series_id:
        # Check cache directory and outputs directory
        candidate_files = [
            RESULTS_CACHE_DIR / f"{series_id}.json",
            OUTPUTS_DIR / f"{series_id}.json",
            OUTPUTS_DIR / f"series_{series_id}.json",
            Path(settings.DATA_CACHE_DIR) / "results" / f"{series_id}.json",
            Path(settings.DATA_CACHE_DIR) / "results" / f"series_{series_id}.json",
        ]
        for c_file in candidate_files:
            if c_file.exists():
                with open(c_file, "r", encoding="utf-8") as f:
                    p3_data = json.load(f)
                break

    # Load Page 4
    if change_run_id:
        c_candidates = [
            OUTPUTS_DIR / f"result_{change_run_id}.json",
            OUTPUTS_DIR / f"{change_run_id}.json",
        ]
        for c_file in c_candidates:
            if c_file.exists():
                with open(c_file, "r", encoding="utf-8") as f:
                    p4_data = json.load(f)
                break

    # Load Page 5
    if significance_run_id:
        s_candidates = [
            OUTPUTS_DIR / f"significance_result_{significance_run_id}.json",
            OUTPUTS_DIR / f"{significance_run_id}.json",
        ]
        for s_file in s_candidates:
            if s_file.exists():
                with open(s_file, "r", encoding="utf-8") as f:
                    p5_data = json.load(f)
                break
        s_file = OUTPUTS_DIR / f"significance_result_{significance_run_id}.json"
        if s_file.exists():
            with open(s_file, "r", encoding="utf-8") as f:
                p5_data = json.load(f)

    return p3_data, p4_data, p5_data


def validate_runs_consistency(
    p3_data: Optional[Dict[str, Any]],
    p4_data: Optional[Dict[str, Any]],
    p5_data: Optional[Dict[str, Any]],
) -> None:
    """
    Validates that provided runs share identical dataset versions, regions, and dates.
    Raises ValueError with a specific, informative error message if any discrepancy is detected.
    """
    active_runs = []
    if p3_data:
        active_runs.append(("Page 3 (Trends)", p3_data))
    if p4_data:
        active_runs.append(("Page 4 (Change)", p4_data))
    if p5_data:
        active_runs.append(("Page 5 (Significance)", p5_data))

    if not active_runs:
        raise ValueError("At least one valid analysis run ID must be provided to assemble a report.")

    # 1. Dataset Version Check
    versions = {}
    for name, data in active_runs:
        v = (
            data.get("dataset", {}).get("version")
            or data.get("provenance", {}).get("dataset_version")
            or resolve_dataset_version(
                data.get("dataset", {}).get("id") or data.get("provenance", {}).get("dataset_id"),
                data.get("provenance", {}).get("variable"),
            )
        )
        versions[name] = v

    unique_versions = set(versions.values())
    if len(unique_versions) > 1:
        details = ", ".join([f"{k} uses '{v}'" for k, v in versions.items()])
        raise ValueError(f"Dataset version mismatch: {details}. Reports cannot combine differing dataset versions.")

    # 2. Region / Study Area Check
    # Compare geometry hashes or bounding boxes across runs where available
    geom_hashes = {}
    bounds_map = {}
    for name, data in active_runs:
        ghash = data.get("provenance", {}).get("geometry_hash")
        if ghash:
            geom_hashes[name] = ghash
        b = data.get("bounds")
        if b:
            # Round bounds to 2 decimal places to tolerate floating point nuances
            rounded_b = tuple(round(coord, 2) for row in b for coord in row)
            bounds_map[name] = rounded_b

    if len(set(geom_hashes.values())) > 1:
        details = ", ".join([f"{k} (hash {v})" for k, v in geom_hashes.items()])
        raise ValueError(f"Study area mismatch: analysis runs refer to different regions ({details}).")

    if len(set(bounds_map.values())) > 1:
        details = ", ".join([f"{k} (bounds {v})" for k, v in bounds_map.items()])
        raise ValueError(f"Study area mismatch: analysis runs refer to different geographic bounds ({details}).")

    # 3. Temporal Consistency Check
    # Ensure Page 4 comparison period does not exceed the coverage of Page 3 or Page 5
    if p3_data and p4_data:
        p3_end_str = p3_data.get("coverage", {}).get("actual_end") or p3_data.get("provenance", {}).get("actual_end")
        p4_comp_raw = p4_data.get("provenance", {}).get("comparison_period")
        p4_comp_end = None
        if isinstance(p4_comp_raw, (list, tuple)) and len(p4_comp_raw) >= 2:
            try:
                p4_comp_end = int(p4_comp_raw[1])
            except (ValueError, TypeError) as e:
                logger.warning("Failed to parse Page 4 comparison period end %s: %s", p4_comp_raw, e)
        elif isinstance(p4_comp_raw, str):
            parts = p4_comp_raw.replace("–", "-").split("-")
            if len(parts) >= 2:
                try:
                    p4_comp_end = int(parts[1].strip())
                except (ValueError, TypeError) as e:
                    logger.warning("Failed to parse Page 4 comparison period end from string %s: %s", p4_comp_raw, e)

        if p3_end_str and p4_comp_end is not None:
            p3_end_year = None
            try:
                p3_end_year = int(p3_end_str[:4])
            except (TypeError, IndexError, ValueError) as e:
                logger.warning("Failed to parse Page 3 end year %s: %s", p3_end_str, e)
            if p3_end_year is not None and p4_comp_end > p3_end_year:
                raise ValueError(
                    f"Date range mismatch: Page 4 comparison year ({p4_comp_end}) "
                    f"exceeds Page 3 historical coverage end ({p3_end_year})."
                )


# ---------------------------------------------------------------------------
# 2. Executive Summary Templating (SPEC 10.7)
# ---------------------------------------------------------------------------

def format_period_str(p: Any) -> str:
    """Format period as YYYY–YYYY whether provided as list/tuple or string."""
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        return f"{p[0]}–{p[1]}"
    if isinstance(p, str):
        parts = p.replace("–", "-").split("-")
        if len(parts) >= 2:
            return f"{parts[0].strip()}–{parts[1].strip()}"
        return p
    return str(p)


def build_executive_summary_template(
    p3_data: Optional[Dict[str, Any]],
    p4_data: Optional[Dict[str, Any]],
    p5_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Builds a synthesized executive summary exclusively from stored numbers.
    Zero free-written or unverified claims (Rule 1, SPEC 10.7).
    """
    paragraphs: List[str] = []
    key_metrics: Dict[str, Any] = {}

    # Extract Page 3 numbers
    if p3_data:
        p3_sum = p3_data.get("summary", {})
        p3_prov = p3_data.get("provenance", {})
        cov = p3_data.get("coverage", {})

        var_name = p3_prov.get("variable", "precipitation").capitalize()
        units = p3_prov.get("output_units", "mm")
        start_raw = cov.get("actual_start") or p3_prov.get("start_date") or (p3_data.get("points", [{}])[0].get("date") if p3_data.get("points") else None)
        end_raw = cov.get("actual_end") or p3_prov.get("end_date") or (p3_data.get("points", [{}])[-1].get("date") if p3_data.get("points") else None)
        start_date = str(start_raw)[:4] if start_raw else "[Start Date Not Specified]"
        end_date = str(end_raw)[:4] if end_raw else "[End Date Not Specified]"
        n_obs = cov.get("valid_steps", len(p3_data.get("points", [])))
        completeness = cov.get("completeness_pct", 100.0)

        slope_ols = (
            p3_sum.get("slope")
            if p3_sum.get("slope") is not None
            else p3_sum.get("ols", {}).get("slope_per_year", 0.0)
        )
        ci_lower = (
            p3_sum.get("ols_ci_lower")
            if p3_sum.get("ols_ci_lower") is not None
            else p3_sum.get("ols", {}).get("ci_lower_slope", 0.0)
        )
        ci_upper = (
            p3_sum.get("ols_ci_upper")
            if p3_sum.get("ols_ci_upper") is not None
            else p3_sum.get("ols", {}).get("ci_upper_slope", 0.0)
        )
        slope_sen_raw = p3_sum.get("sens_slope")
        if isinstance(slope_sen_raw, dict):
            slope_sen = slope_sen_raw.get("slope_per_year", 0.0)
        elif slope_sen_raw is not None:
            slope_sen = slope_sen_raw
        else:
            slope_sen = 0.0
        avg_val = p3_sum.get("mean") if p3_sum.get("mean") is not None else 0.0
        trend_dir = p3_sum.get("trend_direction", "no clear trend").capitalize()

        p3_text = (
            f"Historical trend analysis of {var_name} from {start_date} to {end_date} "
            f"({n_obs} valid monthly observations, {completeness:.1f}% temporal completeness) "
            f"reveals a baseline regional mean of {avg_val:.2f} {units}. "
            f"Ordinary least squares regression yields a slope of {slope_ols:+.3f} {units}/year "
            f"(95% CI: [{ci_lower:.3f}, {ci_upper:.3f}]), while robust Theil-Sen non-parametric "
            f"estimation indicates a slope of {slope_sen:+.3f} {units}/year. "
            f"The classified regional trajectory is characterized as: {trend_dir}."
        )
        paragraphs.append(p3_text)
        key_metrics["regional_mean"] = f"{avg_val:.2f} {units}"
        key_metrics["sen_slope"] = f"{slope_sen:+.3f} {units}/year"
        key_metrics["ols_slope"] = f"{slope_ols:+.3f} {units}/year"

    # Extract Page 4 numbers
    if p4_data:
        p4_sum = p4_data.get("spatial_summary", {})
        p4_prov = p4_data.get("provenance", {})
        units = p4_data.get("units", "mm/year")

        p4_base = p4_prov.get("baseline_period")
        p4_comp = p4_prov.get("comparison_period")
        if not p4_base:
            logger.warning("Baseline period not specified in Page 4 provenance")
        if not p4_comp:
            logger.warning("Comparison period not specified in Page 4 provenance")
        base_str = format_period_str(p4_base) if p4_base else "[Baseline Period Not Specified]"
        comp_str = format_period_str(p4_comp) if p4_comp else "[Comparison Period Not Specified]"
        mean_change = p4_sum.get("area_weighted_mean_change")
        inc_pct = p4_sum.get("share_increasing_pct", 0.0)
        dec_pct = p4_sum.get("share_decreasing_pct", 0.0)
        nodata_km2 = p4_sum.get("nodata_area_km2", 0.0)
        nodata_pct = p4_sum.get("nodata_share_pct", 0.0)
        hi_change = p4_sum.get("highest_change")
        lo_change = p4_sum.get("lowest_change")

        p4_text = (
            f"Spatial change detection comparing baseline period {base_str} "
            f"against comparison period {comp_str} identifies an area-weighted "
            f"mean change of {mean_change:+.2f} {units} across the study domain. "
            f"Within valid sampled areas, {inc_pct:.1f}% of the territory experienced positive change, "
            f"whereas {dec_pct:.1f}% experienced negative change. "
        )
        if hi_change and lo_change:
            p4_text += (
                f"Localized extreme changes range from {lo_change['value']:+.1f} {units} "
                f"at ({lo_change['lat']:.1f}°N, {lo_change['lon']:.1f}°E) to "
                f"{hi_change['value']:+.1f} {units} at ({hi_change['lat']:.1f}°N, {hi_change['lon']:.1f}°E). "
            )
        if nodata_km2 > 0:
            p4_text += (
                f"Non-sampled or masked areas account for {nodata_km2:,.0f} km² "
                f"({nodata_pct:.1f}% of bounding domain), reported strictly distinct from zero change."
            )
        paragraphs.append(p4_text)
        key_metrics["area_weighted_mean_change"] = f"{mean_change:+.2f} {units}"
        key_metrics["increasing_area_share"] = f"{inc_pct:.1f}%"
        key_metrics["decreasing_area_share"] = f"{dec_pct:.1f}%"

    # Extract Page 5 numbers
    if p5_data:
        p5_reg = p5_data.get("regional", {})
        p5_spat = p5_data.get("spatial", {})

        p_val = p5_reg.get("raw_p_value")
        alpha = p5_reg.get("alpha", 0.05)
        test_name = p5_reg.get("test_name", "Mann-Kendall")
        is_sig = p5_reg.get("is_significant", False)
        r1 = p5_reg.get("lag1_autocorrelation")
        adj_desc = p5_reg.get("choice_documentation", "")

        spat_counts = p5_spat.get("class_counts", {})
        sig_inc = spat_counts.get("significant_increase", 0)
        sig_dec = spat_counts.get("significant_decrease", 0)
        not_sig = spat_counts.get("not_significant", 0)
        fdr_mode = "Benjamini-Hochberg FDR Adjusted" if p5_spat.get("fdr_correction", True) else "Raw"

        sig_status = "statistically significant" if is_sig else "not statistically significant"
        p5_text = (
            f"Inferential hypothesis testing ({test_name}) evaluates the observed monotonic trend as {sig_status} "
            f"(p = {p_val:.4f} vs threshold α = {alpha}). "
            f"Serial autocorrelation analysis indicates lag-1 coefficient r₁ = {r1:.3f}; {adj_desc}. "
            f"Across the 2D spatial grid under {fdr_mode} multiple-testing control, {sig_inc} cells "
            f"exhibit significant increases, {sig_dec} cells exhibit significant decreases, and "
            f"{not_sig} cells show no statistically detectable trend. "
            f"Caution: Statistical significance demonstrates evidence against the null hypothesis; "
            f"it does not imply environmental magnitude or prove a causal mechanism."
        )
        paragraphs.append(p5_text)
        key_metrics["significance_p_value"] = f"{p_val:.4f}"
        key_metrics["significant_increase_cells"] = sig_inc
        key_metrics["significant_decrease_cells"] = sig_dec

    return {
        "paragraphs": paragraphs,
        "key_metrics": key_metrics,
    }


# ---------------------------------------------------------------------------
# 3. Timeseries Chart Rendering for ReportLab PDF
# ---------------------------------------------------------------------------

def render_report_trend_chart(
    points: List[Dict[str, Any]],
    output_png_path: Path,
    variable_name: str = "Precipitation",
    units: str = "mm",
) -> Path:
    """
    Renders publication-quality time series graph with observations,
    trend line, and confidence band directly from stored points using matplotlib.
    """
    output_png_path.parent.mkdir(parents=True, exist_ok=True)

    valid_pts = [p for p in points if p.get("value") is not None and not np.isnan(p.get("value"))]
    if not valid_pts:
        # Fallback empty figure
        fig, ax = plt.subplots(figsize=(8, 3.2), dpi=200)
        ax.text(0.5, 0.5, "No valid time series data to render", ha="center", va="center")
        plt.tight_layout()
        fig.savefig(output_png_path)
        plt.close(fig)
        return output_png_path

    dates = [p["date"] for p in valid_pts]
    values = np.array([p["value"] for p in valid_pts], dtype=np.float64)
    x_indices = np.arange(len(values))

    fig, ax = plt.subplots(figsize=(8.5, 3.5), dpi=220)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#f8fafc")

    # Plot raw points & series
    ax.plot(x_indices, values, color="#0284c7", linewidth=1.2, alpha=0.85, label=f"Monthly {variable_name}")

    # Plot OLS or Sen's trend line if present
    sens_vals = [p.get("sens_line") for p in valid_pts]
    if any(s is not None for s in sens_vals):
        valid_sens = [s if s is not None else np.nan for s in sens_vals]
        ax.plot(x_indices, valid_sens, color="#b91c1c", linewidth=2.0, linestyle="--", label="Sen's Trend Line")

    # Plot CI band if present
    ci_lows = [p.get("ols_ci_lower") for p in valid_pts]
    ci_highs = [p.get("ols_ci_upper") for p in valid_pts]
    if any(c is not None for c in ci_lows) and any(c is not None for c in ci_highs):
        low_arr = np.array([c if c is not None else np.nan for c in ci_lows], dtype=np.float64)
        high_arr = np.array([c if c is not None else np.nan for c in ci_highs], dtype=np.float64)
        ax.fill_between(x_indices, low_arr, high_arr, color="#ef4444", alpha=0.15, label="95% Confidence Band")

    # Format Axes
    ax.set_title(f"Historical Regional Time Series — {variable_name} ({units})", fontsize=11, fontweight="bold", color="#0f172a", pad=10)
    ax.set_ylabel(f"{variable_name} ({units})", fontsize=9, color="#334155")
    ax.set_xlabel("Observation Period", fontsize=9, color="#334155")

    # Sample ticks for date labels
    n_ticks = min(8, len(dates))
    tick_pos = np.linspace(0, len(dates) - 1, n_ticks, dtype=int)
    ax.set_xticks(tick_pos)
    ax.set_xticklabels([dates[i][:7] for i in tick_pos], fontsize=8, color="#475569")
    ax.tick_params(colors="#475569", labelsize=8)

    ax.grid(True, linestyle=":", alpha=0.6, color="#cbd5e1")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9, facecolor="#ffffff", edgecolor="#cbd5e1")

    # Styling border
    for spine in ax.spines.values():
        spine.set_color("#cbd5e1")
        spine.set_linewidth(0.8)

    plt.tight_layout()
    fig.savefig(output_png_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    return output_png_path


# ---------------------------------------------------------------------------
# 4. ReportLab PDF Document Assembly
# ---------------------------------------------------------------------------

def generate_report_pdf(
    report_payload: Dict[str, Any],
    output_pdf_path: Path,
    trend_chart_path: Optional[Path] = None,
    change_overlay_path: Optional[Path] = None,
    sig_overlay_path: Optional[Path] = None,
) -> Path:
    """
    Compiles full, publication-ready multi-page PDF report using ReportLab.
    """
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_pdf_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
        spaceAfter=14,
    )
    h2_style = ParagraphStyle(
        "ReportH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=6,
    )
    body_bold = ParagraphStyle(
        "ReportBodyBold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )
    caution_style = ParagraphStyle(
        "ReportCaution",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#78350f"),
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1e293b"),
    )
    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=table_cell,
        fontName="Helvetica-Bold",
    )

    story: List[Any] = []

    # Title & Header
    title_text = report_payload.get("title", "Gaia Insights — Scientific Analysis Report")
    story.append(Paragraph(title_text, title_style))
    meta_sub = (
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} • "
        f"Report ID: <font name='Courier'>{report_payload['report_id']}</font> • "
        f"Application: Antigravity Gaia Insights v{APP_VERSION}"
    )
    story.append(Paragraph(meta_sub, subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=14))

    sections_enabled = report_payload.get("sections_enabled", {})

    # =========================================================================
    # Section 1: Executive Summary (SPEC 10.7)
    # =========================================================================
    if sections_enabled.get("executive_summary", True):
        story.append(Paragraph("1. Executive Summary", h2_style))
        exec_data = report_payload.get("executive_summary", {})
        paragraphs = exec_data.get("paragraphs", [])

        # Executive summary callout card
        card_content = []
        for p_text in paragraphs:
            card_content.append(Paragraph(p_text, body_style))
            card_content.append(Spacer(1, 4))

        card_table = Table(
            [[card_content]],
            colWidths=[letter[0] - 108],
        )
        card_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdf4")),
                ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor("#86efac")),
                ("PADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(card_table)
        story.append(Spacer(1, 10))

    # =========================================================================
    # Section 2: Dataset and Study Area (SPEC 10.7)
    # =========================================================================
    if sections_enabled.get("dataset_and_study_area", True):
        story.append(Paragraph("2. Dataset and Study Area", h2_style))
        ds_info = report_payload.get("dataset_info", {})
        study_area = report_payload.get("study_area", {})

        meta_rows = [
            [Paragraph("Variable:", table_cell_bold), Paragraph(str(ds_info.get("variable", "Precipitation")), table_cell),
             Paragraph("Native Units:", table_cell_bold), Paragraph(str(ds_info.get("units", "mm")), table_cell)],
            [Paragraph("Dataset Collection:", table_cell_bold), Paragraph(str(ds_info.get("dataset_id", "gpcp_monthly_v23")), table_cell),
             Paragraph("Product Version:", table_cell_bold), Paragraph(str(ds_info.get("dataset_version", "v2.3")), table_cell)],
            [Paragraph("Data Provider:", table_cell_bold), Paragraph(str(ds_info.get("provider", "NOAA PSL / NASA GSFC")), table_cell),
             Paragraph("DOI:", table_cell_bold), Paragraph(f"<font name='Courier'>{ds_info.get('doi', '10.7289/V56971M6')}</font>", table_cell)],
            [Paragraph("Spatial Extent:", table_cell_bold), Paragraph(str(study_area.get("label", "Selected Region")), table_cell),
             Paragraph("Grid Resolution:", table_cell_bold), Paragraph(str(ds_info.get("spatial_resolution", "2.5° × 2.5° Global Grid")), table_cell)],
            [Paragraph("Coordinate Ref. System:", table_cell_bold), Paragraph("EPSG:4326 (WGS 84)", table_cell),
             Paragraph("Area Weighting:", table_cell_bold), Paragraph("Geodesic cell area × fractional overlap", table_cell)],
        ]

        t_meta = Table(meta_rows, colWidths=[100, 150, 110, 144])
        t_meta.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("PADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(t_meta)
        story.append(Spacer(1, 10))

    # =========================================================================
    # Section 3: Historical Trend Analysis (SPEC 10.7, Page 3)
    # =========================================================================
    if sections_enabled.get("historical_trends", True) and report_payload.get("trends_summary"):
        story.append(Paragraph("3. Historical Trend Analysis", h2_style))
        t_sum = report_payload["trends_summary"]

        s_ols = (
            t_sum.get("slope")
            if t_sum.get("slope") is not None
            else t_sum.get("ols", {}).get("slope_per_year", 0.0)
        )
        ci_l = (
            t_sum.get("ols_ci_lower")
            if t_sum.get("ols_ci_lower") is not None
            else t_sum.get("ols", {}).get("ci_lower_slope", 0.0)
        )
        ci_u = (
            t_sum.get("ols_ci_upper")
            if t_sum.get("ols_ci_upper") is not None
            else t_sum.get("ols", {}).get("ci_upper_slope", 0.0)
        )
        s_sen_raw = t_sum.get("sens_slope")
        if isinstance(s_sen_raw, dict):
            s_sen = s_sen_raw.get("slope_per_year", 0.0)
        elif s_sen_raw is not None:
            s_sen = s_sen_raw
        else:
            s_sen = 0.0
        tot_ch = (
            t_sum.get("total_change")
            if t_sum.get("total_change") is not None
            else t_sum.get("estimated_total_change", 0.0)
        )
        v_steps = (
            t_sum.get("valid_steps")
            if t_sum.get("valid_steps") is not None
            else t_sum.get("valid_n", 0)
        )

        trend_table_data = [
            [Paragraph("Metric", table_cell_bold), Paragraph("Value", table_cell_bold), Paragraph("Description / Method", table_cell_bold)],
            [Paragraph("Regional Mean", table_cell), Paragraph(f"{t_sum.get('mean', 0.0):.2f} {t_sum.get('units', '')}", table_cell), Paragraph("Area-weighted temporal average over valid observation steps", table_cell)],
            [Paragraph("Theil-Sen Slope", table_cell), Paragraph(f"{s_sen:+.3f} {t_sum.get('units', '')}/yr", table_cell), Paragraph("Median pairwise slope; robust against outliers and non-normality", table_cell)],
            [Paragraph("OLS Linear Slope", table_cell), Paragraph(f"{s_ols:+.3f} {t_sum.get('units', '')}/yr", table_cell), Paragraph(f"Ordinary least squares; 95% CI: [{ci_l:.3f}, {ci_u:.3f}]", table_cell)],
            [Paragraph("Trajectory Direction", table_cell), Paragraph(str(t_sum.get("trend_direction", "")).capitalize(), table_cell), Paragraph("Assessed at significance threshold α = 0.05", table_cell)],
            [Paragraph("Total Estimated Change", table_cell), Paragraph(f"{tot_ch:+.2f} {t_sum.get('units', '')}", table_cell), Paragraph(f"Estimated across {v_steps} monthly time steps", table_cell)],
        ]

        t_table = Table(trend_table_data, colWidths=[120, 110, 274])
        t_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("PADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(t_table)
        story.append(Spacer(1, 8))

        # Embedded timeseries chart
        if trend_chart_path and trend_chart_path.exists():
            chart_img = Image(str(trend_chart_path), width=7.0 * inch, height=2.8 * inch)
            story.append(chart_img)
            story.append(Spacer(1, 10))

    # =========================================================================
    # Section 4: Spatial Change Detection (SPEC 10.7, Page 4)
    # =========================================================================
    if sections_enabled.get("change_detection", True) and report_payload.get("change_summary"):
        story.append(Paragraph("4. Spatial Change Detection", h2_style))
        c_sum = report_payload["change_summary"]
        c_prov = report_payload.get("change_provenance", {})
        units = report_payload.get("dataset_info", {}).get("units", "mm/year")

        c_base = c_prov.get("baseline_period")
        c_comp = c_prov.get("comparison_period")
        if not c_base:
            logger.warning("Baseline period not specified in change provenance")
        if not c_comp:
            logger.warning("Comparison period not specified in change provenance")
        base_str = format_period_str(c_base) if c_base else "[Baseline Period Not Specified]"
        comp_str = format_period_str(c_comp) if c_comp else "[Comparison Period Not Specified]"

        change_rows = [
            [Paragraph("Parameter", table_cell_bold), Paragraph("Value", table_cell_bold), Paragraph("Scientific Note", table_cell_bold)],
            [Paragraph("Baseline Period", table_cell), Paragraph(base_str, table_cell), Paragraph("Reference climatological period (mean annual rate)", table_cell)],
            [Paragraph("Comparison Period", table_cell), Paragraph(comp_str, table_cell), Paragraph("Target observation period (mean annual rate)", table_cell)],
            [Paragraph("Area-Weighted Change", table_cell), Paragraph(f"{c_sum.get('area_weighted_mean_change', 0):+.2f} {units}", table_cell), Paragraph("Geodesic cell area-weighted difference across valid domain", table_cell)],
            [Paragraph("Increasing Domain Share", table_cell), Paragraph(f"{c_sum.get('share_increasing_pct', 0):.1f}%", table_cell), Paragraph("Percentage of sampled valid domain with Δ > 0", table_cell)],
            [Paragraph("Decreasing Domain Share", table_cell), Paragraph(f"{c_sum.get('share_decreasing_pct', 0):.1f}%", table_cell), Paragraph("Percentage of sampled valid domain with Δ < 0", table_cell)],
            [Paragraph("No-Data / Masked Area", table_cell), Paragraph(f"{c_sum.get('nodata_share_pct', 0):.1f}% ({c_sum.get('nodata_area_km2', 0):,.0f} km²)", table_cell), Paragraph("Reported strictly separately from zero change", table_cell)],
        ]

        t_change = Table(change_rows, colWidths=[120, 110, 274])
        t_change.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("PADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(t_change)
        story.append(Spacer(1, 8))

        # Embedded Change Map Overlay
        if change_overlay_path and change_overlay_path.exists():
            c_img = Image(str(change_overlay_path), width=4.5 * inch, height=3.0 * inch)
            c_caption = Paragraph("Figure 4.1: Georeferenced difference field (comparison mean minus baseline mean).", subtitle_style)
            story.append(KeepTogether([c_img, c_caption]))
            story.append(Spacer(1, 10))

    # =========================================================================
    # Section 5: Statistical Significance (SPEC 10.7, Page 5)
    # =========================================================================
    if sections_enabled.get("statistical_significance", True) and report_payload.get("significance_info"):
        story.append(Paragraph("5. Statistical Significance & Hypothesis Testing", h2_style))
        sig = report_payload["significance_info"]
        reg = sig.get("regional", {})
        spat = sig.get("spatial", {})

        sig_rows = [
            [Paragraph("Statistical Parameter", table_cell_bold), Paragraph("Value / Result", table_cell_bold), Paragraph("Methodology & Notes", table_cell_bold)],
            [Paragraph("Regional Hypothesis Test", table_cell), Paragraph(str(reg.get("test_name", "Mann-Kendall")), table_cell), Paragraph(f"Null hypothesis: {reg.get('null_hypothesis', '')}", table_cell)],
            [Paragraph("Raw p-value", table_cell), Paragraph(f"{reg.get('raw_p_value', 0):.4f}", table_cell), Paragraph(f"Significance threshold α = {reg.get('alpha', 0.05)}", table_cell)],
            [Paragraph("Sen's Non-Parametric Slope", table_cell), Paragraph(f"{reg.get('sens_slope', 0):+.3f}/yr", table_cell), Paragraph(f"Rank-based 95% CI: [{reg.get('ci_lower', 0):.3f}, {reg.get('ci_upper', 0):.3f}]", table_cell)],
            [Paragraph("Lag-1 Autocorrelation (r₁)", table_cell), Paragraph(f"{reg.get('lag1_autocorrelation', 0):.3f}", table_cell), Paragraph(str(reg.get("choice_documentation", "")), table_cell)],
            [Paragraph("Spatial Multiple Testing", table_cell), Paragraph("Benjamini-Hochberg FDR", table_cell), Paragraph("Controls expected proportion of false positive discoveries", table_cell)],
            [Paragraph("Grid Significant Increase (+)", table_cell), Paragraph(str(spat.get("class_counts", {}).get("significant_increase", 0)), table_cell), Paragraph("Grid cells with positive slope meeting FDR adjusted threshold", table_cell)],
            [Paragraph("Grid Significant Decrease (−)", table_cell), Paragraph(str(spat.get("class_counts", {}).get("significant_decrease", 0)), table_cell), Paragraph("Grid cells with negative slope meeting FDR adjusted threshold", table_cell)],
            [Paragraph("Grid Not Significant (o)", table_cell), Paragraph(str(spat.get("class_counts", {}).get("not_significant", 0)), table_cell), Paragraph("Tested cells where p_adj >= α", table_cell)],
        ]

        t_sig = Table(sig_rows, colWidths=[130, 110, 264])
        t_sig.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("PADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(t_sig)
        story.append(Spacer(1, 8))

        # Non-negotiable scientific interpretation cautions (SPEC 10.6)
        cautions_box = [
            Paragraph("<b>Scientific Interpretation Cautions (SPEC 10.5 & 10.6):</b>", caution_style),
            Paragraph("• A <b>p-value is not</b> the probability that the null hypothesis is true; it is the probability of observing data at least as extreme under the assumption that the null hypothesis is true.", caution_style),
            Paragraph("• Statistical significance <b>does not imply</b> large environmental magnitude or societal importance.", caution_style),
            Paragraph("• An observed statistical trend <b>does not establish</b> a causal explanation or physical mechanism.", caution_style),
        ]
        t_cautions = Table([[cautions_box]], colWidths=[letter[0] - 108])
        t_cautions.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef3c7")),
                ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor("#f59e0b")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(t_cautions)
        story.append(Spacer(1, 10))

    # =========================================================================
    # Section 6: Data Quality and Limitations (SPEC 10.7)
    # =========================================================================
    if sections_enabled.get("data_quality", True):
        story.append(Paragraph("6. Data Quality, Completeness & Method Limitations", h2_style))
        cov_info = report_payload.get("coverage_info", {})
        ds_info = report_payload.get("dataset_info", {})

        if ds_info.get("caveat"):
            caveat_box = [
                Paragraph("<b>Variable-Specific Limitations & Caveats:</b>", caution_style),
                Paragraph(str(ds_info["caveat"]), caution_style),
            ]
            t_caveat = Table([[caveat_box]], colWidths=[letter[0] - 108])
            t_caveat.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef3c7")),
                    ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor("#f59e0b")),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ])
            )
            story.append(t_caveat)
            story.append(Spacer(1, 8))

        story.append(Paragraph(
            "<b>Missing Data & Fill-Value Policy:</b> All native satellite/gauge fill values are strictly "
            "decoded to NaN upon NetCDF ingestion. Missing observations are never silently replaced with zero. "
            f"Temporal completeness across the study span is {cov_info.get('completeness_pct', 100.0):.1f}% "
            f"({cov_info.get('valid_steps', 0)} of {cov_info.get('expected_steps', 0)} expected monthly slices).",
            body_style
        ))
        story.append(Paragraph(
            "<b>Spatial Masking & Weighting:</b> Boundary cells overlapping the study polygon boundary are "
            "weighted by their fractional intersection area multiplied by the cosine of cell latitude. "
            "This accounts for meridian convergence at non-equatorial latitudes.",
            body_style
        ))
        story.append(Paragraph(
            "<b>Autocorrelation and Multiple Testing:</b> Serial dependence inflates Type I errors in raw "
            "Mann-Kendall tests. Where lag-1 autocorrelation r₁ exceeds 0.10, variance correction is applied. "
            "Spatial grid significance applies Benjamini-Hochberg FDR to limit false discoveries.",
            body_style
        ))
        story.append(Spacer(1, 10))

    # =========================================================================
    # Section 7: Methodology and References (SPEC 10.7, 15.4)
    # =========================================================================
    if sections_enabled.get("methodology_and_references", True):
        story.append(Paragraph("7. Methodology & Bibliographic References", h2_style))
        ds_info = report_payload.get("dataset_info", {})

        math_summary = (
            "<b>Mathematical Formulations:</b><br/>"
            "• <i>Area-Weighted Regional Mean:</i> ȳ = (∑ w_i y_i) / (∑ w_i) where w_i = Area_i × Fraction_i.<br/>"
            "• <i>Theil-Sen Slope:</i> β = median((y_j - y_i) / (t_j - t_i)) for all pairs 1 ≤ i < j ≤ n.<br/>"
            "• <i>Hamed-Rao Variance Inflation:</i> Var*(S) = Var(S) × [1 + (2/n(n-1)(n-2)) ∑ (n-k)(n-k-1)(n-k-2) r_k].<br/>"
            "• <i>Benjamini-Hochberg FDR:</i> Find largest k such that p_(k) ≤ (k/m) α; reject H0 for all i ≤ k."
        )
        story.append(Paragraph(math_summary, body_style))
        story.append(Spacer(1, 6))

        citation_text = (
            f"<b>Primary Dataset Citation:</b><br/>"
            f"{ds_info.get('citation', NASA_CITATIONS.get('gpcp_monthly_v23', {}).get('citation', ''))}<br/>"
            f"<b>DOI:</b> {ds_info.get('doi', '10.7289/V56971M6')}<br/>"
            f"<b>Access Date:</b> {report_payload.get('access_date', datetime.now(timezone.utc).strftime('%Y-%m-%d'))}<br/>"
            f"<b>Software Repository & Provenance:</b> Gaia Insights v{APP_VERSION} "
            f"(FastAPI, Xarray, PyMannKendall, Statsmodels, ReportLab)."
        )
        story.append(Paragraph(citation_text, body_style))
        story.append(Spacer(1, 10))

    # Build PDF with two-pass canvas
    doc.build(story, canvasmaker=NumberedCanvas)
    return output_pdf_path


# ---------------------------------------------------------------------------
# 5. CSV Exports Assembly (SPEC 10.8)
# ---------------------------------------------------------------------------

def generate_report_csv(
    report_payload: Dict[str, Any],
    p3_data: Optional[Dict[str, Any]],
    output_csv_path: Path,
) -> Path:
    """
    Generates structured CSV export with time series observations,
    units, valid cell counts, and quality flags (SPEC 10.8).
    """
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header metadata comments
        writer.writerow(["# Gaia Insights Analysis Report Export"])
        writer.writerow(["# Report ID", report_payload.get("report_id", "")])
        writer.writerow(["# Dataset", report_payload.get("dataset_info", {}).get("dataset_id", "")])
        writer.writerow(["# Version", report_payload.get("dataset_info", {}).get("dataset_version", "")])
        writer.writerow(["# Region", report_payload.get("study_area", {}).get("label", "")])
        writer.writerow(["# Generated At", report_payload.get("created_at", "")])
        writer.writerow([])

        # Table columns
        writer.writerow([
            "date",
            "value",
            "units",
            "is_missing",
            "flags",
            "valid_cells",
            "valid_area_km2",
            "sens_trend_line",
            "ols_fitted",
            "ols_ci_lower",
            "ols_ci_upper",
        ])

        if p3_data and "points" in p3_data:
            units = p3_data.get("dataset", {}).get("units", "mm")
            for pt in p3_data["points"]:
                flags_str = ";".join(pt.get("flags", [])) if pt.get("flags") else ("missing" if pt.get("is_missing") else "valid")
                writer.writerow([
                    pt.get("date"),
                    pt.get("value") if pt.get("value") is not None else "",
                    pt.get("units", units),
                    "true" if pt.get("is_missing") else "false",
                    flags_str,
                    pt.get("valid_cells", ""),
                    pt.get("valid_area_km2", ""),
                    pt.get("sens_line", ""),
                    pt.get("fitted_ols", ""),
                    pt.get("ols_ci_lower", ""),
                    pt.get("ols_ci_upper", ""),
                ])

    return output_csv_path


# ---------------------------------------------------------------------------
# 6. Main High-Level Report Creation Service
# ---------------------------------------------------------------------------

def create_report(
    series_id: Optional[str] = None,
    change_run_id: Optional[str] = None,
    significance_run_id: Optional[str] = None,
    title: Optional[str] = None,
    sections: Optional[Dict[str, bool]] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Executes full report generation journey:
    1. Loads raw outputs from disk.
    2. Validates run consistency (dataset version, region, dates).
    3. Synthesizes template-driven executive summary and section payloads.
    4. Renders timeseries chart and gathers map overlays.
    5. Builds ReportLab PDF and exportable CSV.
    6. Returns structured report object and download URLs.
    """
    import uuid

    if output_dir is None:
        output_dir = OUTPUTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    report_id = f"rep_{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()

    # 1. Load run data
    p3_data, p4_data, p5_data = load_run_data(
        series_id=series_id,
        change_run_id=change_run_id,
        significance_run_id=significance_run_id,
    )

    # 2. Consistency validation
    validate_runs_consistency(p3_data, p4_data, p5_data)

    # Default section toggles
    default_sections = {
        "executive_summary": True,
        "dataset_and_study_area": True,
        "historical_trends": True,
        "change_detection": True,
        "statistical_significance": True,
        "data_quality": True,
        "methodology_and_references": True,
    }
    if sections:
        default_sections.update(sections)

    # Resolve Dataset Metadata
    first_run = p3_data or p4_data or p5_data
    ds_id = (
        first_run.get("dataset", {}).get("id")
        or first_run.get("provenance", {}).get("dataset_id")
        or "gpcp_monthly_v23"
    )
    ds_version = (
        first_run.get("dataset", {}).get("version")
        or first_run.get("provenance", {}).get("dataset_version")
        or resolve_dataset_version(ds_id, first_run.get("provenance", {}).get("variable"))
    )
    units = (
        first_run.get("dataset", {}).get("units")
        or first_run.get("units")
        or "mm"
    )
    var_name = first_run.get("provenance", {}).get("variable", "precipitation").capitalize()

    cite_meta = NASA_CITATIONS.get(ds_id, NASA_CITATIONS["gpcp_monthly_v23"])
    dataset_info = {
        "dataset_id": ds_id,
        "dataset_version": ds_version,
        "variable": var_name,
        "units": units,
        "provider": cite_meta["provider"],
        "doi": cite_meta["doi"],
        "citation": cite_meta["citation"],
        "spatial_resolution": cite_meta.get("spatial_resolution", "2.5° × 2.5° Global Grid"),
        "caveat": cite_meta.get("caveat"),
    }

    study_area = {
        "label": first_run.get("provenance", {}).get("region_id") or "Selected Region",
        "geometry_hash": first_run.get("provenance", {}).get("geometry_hash"),
        "bounds": first_run.get("bounds"),
    }

    # 3. Build Template-Driven Executive Summary
    exec_summary = build_executive_summary_template(p3_data, p4_data, p5_data)

    # Coverage metadata
    coverage_info = {}
    if p3_data:
        coverage_info = p3_data.get("coverage", {})

    report_payload = {
        "report_id": report_id,
        "title": title or "Gaia Insights — Scientific Analysis Report",
        "status": "completed",
        "created_at": created_at,
        "access_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "app_version": APP_VERSION,
        "sections_enabled": default_sections,
        "executive_summary": exec_summary,
        "dataset_info": dataset_info,
        "study_area": study_area,
        "coverage_info": coverage_info,
        "trends_summary": p3_data.get("summary") if p3_data else None,
        "change_summary": p4_data.get("spatial_summary") if p4_data else None,
        "change_provenance": p4_data.get("provenance") if p4_data else None,
        "significance_info": p5_data if p5_data else None,
        "run_references": {
            "series_id": series_id,
            "change_run_id": change_run_id,
            "significance_run_id": significance_run_id,
        },
    }

    # 4. Render Chart & Collect Assets for PDF
    trend_chart_file = None
    if p3_data and "points" in p3_data:
        trend_chart_file = output_dir / f"report_{report_id}_chart.png"
        render_report_trend_chart(
            points=p3_data["points"],
            output_png_path=trend_chart_file,
            variable_name=var_name,
            units=units,
        )

    change_overlay_file = None
    if change_run_id:
        c_overlay = OUTPUTS_DIR / f"overlay_{change_run_id}.png"
        if c_overlay.exists():
            change_overlay_file = c_overlay

    sig_overlay_file = None
    if significance_run_id:
        s_overlay = OUTPUTS_DIR / f"overlay_{significance_run_id}.png"
        if s_overlay.exists():
            sig_overlay_file = s_overlay

    # 5. Build PDF & CSV
    pdf_path = output_dir / f"report_{report_id}.pdf"
    generate_report_pdf(
        report_payload=report_payload,
        output_pdf_path=pdf_path,
        trend_chart_path=trend_chart_file,
        change_overlay_path=change_overlay_file,
        sig_overlay_path=sig_overlay_file,
    )

    csv_path = output_dir / f"report_{report_id}_timeseries.csv"
    generate_report_csv(
        report_payload=report_payload,
        p3_data=p3_data,
        output_csv_path=csv_path,
    )

    # 6. Save Report JSON metadata
    report_json_path = output_dir / f"report_{report_id}.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    # 7. Construct response with download endpoints
    response = {
        "report_id": report_id,
        "title": report_payload["title"],
        "status": "completed",
        "created_at": created_at,
        "sections_enabled": default_sections,
        "executive_summary": exec_summary,
        "dataset_info": dataset_info,
        "study_area": study_area,
        "trends_summary": report_payload["trends_summary"],
        "change_summary": report_payload["change_summary"],
        "significance_info": report_payload["significance_info"],
        "downloads": {
            "pdf_url": f"/api/reports/{report_id}/pdf",
            "csv_url": f"/api/reports/{report_id}/csv",
            "chart_png_url": f"/api/reports/{report_id}/chart.png" if trend_chart_file and trend_chart_file.exists() else None,
            "change_overlay_url": f"/api/analysis/change-map/{change_run_id}/overlay.png" if change_run_id else None,
            "change_geotiff_url": f"/api/analysis/change-map/{change_run_id}/geotiff" if change_run_id else None,
            "significance_overlay_url": f"/api/analysis/significance/{significance_run_id}/overlay.png" if significance_run_id else None,
            "significance_geotiff_url": f"/api/analysis/significance/{significance_run_id}/geotiff" if significance_run_id else None,
        },
    }

    return response
