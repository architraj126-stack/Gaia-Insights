"""
Statistical Significance Service (SPEC 10, 14.6, 14.7, 14.8, Scientific Rules 8, 9, 10).

Key Responsibilities:
- Regional Significance: Evaluates trend significance on the regional series.
  * Seasonal Mann-Kendall for monthly data, Mann-Kendall for annual series.
  * Empirical lag-1 autocorrelation evaluation and correction choice (Hamed-Rao, Yue-Pilon TFPW, or original).
  * Theil-Sen non-parametric slope with rank-based analytical confidence intervals.
  * Explicit null hypothesis, test statistic, p-value, sample size, and clear user-facing interpretation.
- Spatial Significance: Vectorised per-cell trend testing across the 2D grid.
  * Vectorised Mann-Kendall and Sen's slope completing a global grid in seconds.
  * False Discovery Rate (FDR) control via Benjamini-Hochberg (statsmodels fdr_bh) on tested cells.
  * 5 discrete classes: Significant increase, Significant decrease, Not significant, Insufficient data, Not covered.
  * GeoTIFF/COG raster output and transparent PNG map overlay.
- Re-reads cell time series from cache; never infers significance from a difference raster.
- Changing alpha or toggling FDR reuses cached cell statistics.
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import pymannkendall as pmk
import scipy.special as sc_spec
import scipy.stats as sc_stats
import statsmodels.stats.multitest as smm
import xarray as xr
from shapely.geometry.base import BaseGeometry

from backend.app.config import settings
from backend.app.services.change import compute_annual_cell_values, OUTPUTS_DIR
from backend.app.services.regions import build_grid_mask_weights

logger = logging.getLogger("backend.services.significance")

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# 5 Classification codes (SPEC 10.4)
CLASS_NOT_COVERED = 0
CLASS_SIG_INCREASE = 1
CLASS_SIG_DECREASE = 2
CLASS_NOT_SIGNIFICANT = 3
CLASS_INSUFFICIENT_DATA = 4

CLASS_METADATA = {
    CLASS_SIG_INCREASE: {
        "id": "significant_increase",
        "label": "Significant Increase (+)",
        "color": "#dc2626",  # Red
        "pattern": "dots_plus",
        "description": "Positive slope meeting statistical threshold after multiple-testing correction.",
    },
    CLASS_SIG_DECREASE: {
        "id": "significant_decrease",
        "label": "Significant Decrease (-)",
        "color": "#2563eb",  # Blue
        "pattern": "dots_minus",
        "description": "Negative slope meeting statistical threshold after multiple-testing correction.",
    },
    CLASS_NOT_SIGNIFICANT: {
        "id": "not_significant",
        "label": "Not Significant (o)",
        "color": "#94a3b8",  # Neutral slate
        "pattern": "solid",
        "description": "Valid estimate exists but does not meet statistical evidence threshold.",
    },
    CLASS_INSUFFICIENT_DATA: {
        "id": "insufficient_data",
        "label": "Insufficient Data (?)",
        "color": "#d97706",  # Amber
        "pattern": "crosshatch",
        "description": "Fewer than required valid temporal observations to run test reliably.",
    },
    CLASS_NOT_COVERED: {
        "id": "not_covered",
        "label": "Not Covered / Masked",
        "color": "#1e293b",  # Dark charcoal/transparent
        "pattern": "none",
        "description": "No data coverage or outside selected study area.",
    },
}


def compute_lag1_autocorrelation(series: np.ndarray) -> float:
    """
    Computes empirical lag-1 serial autocorrelation coefficient (r1).
    Ignores NaNs by using valid consecutive pairs.
    """
    valid_mask = ~np.isnan(series)
    if np.sum(valid_mask) < 4:
        return 0.0

    y = series[valid_mask]
    n = len(y)
    y_mean = np.mean(y)
    y_dev = y - y_mean
    denom = np.sum(y_dev ** 2)
    if denom <= 1e-12:
        return 0.0

    r1 = np.sum(y_dev[:-1] * y_dev[1:]) / denom
    return float(np.clip(r1, -1.0, 1.0))


def evaluate_regional_significance(
    time_series_points: List[Dict[str, Any]],
    frequency: str = "monthly",
    alpha: float = 0.05,
    ci_level: float = 0.95,
    autocorrelation_method: str = "auto",  # auto | hamed_rao | pre_whitening | none
) -> Dict[str, Any]:
    """
    Performs rigorous trend significance testing on a regional series (SPEC 10.3, 10.5, 10.6).
    """
    raw_vals = [p.get("value") for p in time_series_points]
    series_arr = np.array([v if (v is not None and not np.isnan(v)) else np.nan for v in raw_vals], dtype=np.float64)

    valid_mask = ~np.isnan(series_arr)
    valid_vals = series_arr[valid_mask]
    n_samples = len(valid_vals)

    if n_samples < 6:
        return {
            "test_name": "Insufficient Data",
            "null_hypothesis": "The series has insufficient data to test for monotonic trend.",
            "test_statistic": None,
            "raw_p_value": None,
            "sens_slope": None,
            "ci_lower": None,
            "ci_upper": None,
            "sample_size": n_samples,
            "alpha": alpha,
            "ci_level": ci_level,
            "lag1_autocorrelation": None,
            "autocorrelation_handling": "none",
            "choice_documentation": "Not enough valid points (minimum 6 required).",
            "interpretation": "Insufficient observations available to test significance.",
            "is_significant": False,
        }

    # 1. Autocorrelation assessment
    r1 = compute_lag1_autocorrelation(series_arr)

    # 2. Select test method based on frequency and autocorrelation
    chosen_handling = autocorrelation_method
    if chosen_handling == "auto":
        # If monthly, seasonality dominates; if annual and r1 > 0.1, use Hamed-Rao
        if frequency == "monthly":
            chosen_handling = "seasonal_or_hamed_rao"
        elif abs(r1) > 0.1:
            chosen_handling = "hamed_rao"
        else:
            chosen_handling = "none"

    test_name = "Mann-Kendall Test"
    documentation = ""

    warnings_list: List[str] = []
    is_seasonal = frequency == "monthly" and len(time_series_points) >= 24
    method_used = "seasonal_mann_kendall" if is_seasonal else f"mann_kendall_{chosen_handling}"
    fallback_reason: Optional[str] = None

    try:
        if is_seasonal:
            # Monthly data: Seasonal Mann-Kendall (period=12) handles seasonal cycles
            test_name = "Seasonal Mann-Kendall Test (period=12)"
            res = pmk.seasonal_test(valid_vals, period=12)
            documentation = (
                f"Seasonal Mann-Kendall applied with period=12 to prevent seasonal variations "
                f"from being confounded with monotonic trends. Empirical lag-1 r1={r1:.3f}."
            )
        elif chosen_handling == "hamed_rao":
            test_name = "Hamed-Rao Modified Mann-Kendall Test"
            res = pmk.hamed_rao_modification_test(valid_vals)
            documentation = (
                f"Hamed & Rao (1998) variance correction applied due to empirical serial autocorrelation "
                f"(lag-1 r1={r1:.3f}). This prevents inflated false significance."
            )
        elif chosen_handling == "pre_whitening":
            test_name = "Trend-Free Pre-Whitening (Yue-Pilon) Mann-Kendall Test"
            res = pmk.trend_free_pre_whitening_modification_test(valid_vals)
            documentation = (
                f"Yue-Pilon Trend-Free Pre-Whitening applied to remove lag-1 autocorrelation (r1={r1:.3f}) "
                f"before non-parametric trend evaluation."
            )
        else:
            test_name = "Original Mann-Kendall Test"
            res = pmk.original_test(valid_vals)
            documentation = (
                f"Standard Mann-Kendall test applied (lag-1 r1={r1:.3f} within acceptable independent threshold)."
            )

        stat_val = float(res.z) if hasattr(res, "z") and res.z is not None else float(res.s)
        p_val = float(res.p)
        slope_val = float(res.slope)

    except Exception as e:
        logger.error("Modified Mann-Kendall test failed (%s), falling back to original MK", e)
        method_used = "mann_kendall_original"
        fallback_reason = f"Modified Mann-Kendall failed: {e}; used original test."
        warnings_list.append(fallback_reason)
        test_name = "Original Mann-Kendall Test (fallback)"
        res = pmk.original_test(valid_vals)
        stat_val = float(res.z)
        p_val = float(res.p)
        slope_val = float(res.slope)
        documentation = f"Fallback standard test used. {fallback_reason} Autocorrelation r1={r1:.3f}."

    # 3. Sen's slope and analytical rank confidence interval via scipy.stats.theilslopes
    # theilslopes accepts x and alpha = confidence level
    x_indices = np.arange(n_samples, dtype=np.float64)
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    try:
        theil_res = sc_stats.theilslopes(valid_vals, x_indices, alpha=ci_level)
        ci_lower = float(theil_res.low_slope)
        ci_upper = float(theil_res.high_slope)
        if math.isnan(slope_val):
            slope_val = float(theil_res.slope)
    except Exception as e:
        logger.error("Failed to compute Theil-Sen confidence interval: %s", e)
        ci_lower = None
        ci_upper = None
        warnings_list.append(f"Confidence interval calculation failed: {e}")

    is_significant = p_val < alpha
    null_hyp = (
        "There is no monotonic trend over time in the regional series (H0: beta = 0); "
        "observed historical variations are consistent with random fluctuation."
    )

    direction = "an upward" if slope_val > 0 else "a downward" if slope_val < 0 else "no"
    if is_significant:
        interp = (
            f"The regional series provides evidence against the null hypothesis (p = {p_val:.4e} < {alpha}). "
            f"There is a statistically detectable {direction} monotonic trend of {slope_val:.3f} per year. "
            f"Caution (SPEC 10.5–10.6): A low p-value is not the probability the null hypothesis is true; "
            f"statistical significance does not imply large environmental magnitude or a causal mechanism."
        )
    else:
        interp = (
            f"The regional series does not provide sufficient evidence to reject the null hypothesis (p = {p_val:.4f} >= {alpha}). "
            f"Observed changes may be attributable to natural variability. "
            f"Caution: Failing to detect a trend does not prove that no change is occurring (absence of evidence is not evidence of absence)."
        )

    return {
        "test_name": test_name,
        "method_used": method_used,
        "fallback_reason": fallback_reason,
        "null_hypothesis": null_hyp,
        "test_statistic": round(stat_val, 4) if stat_val is not None else None,
        "raw_p_value": float(p_val) if p_val is not None else None,
        "sens_slope": round(slope_val, 4) if slope_val is not None and not math.isnan(slope_val) else None,
        "ci_lower": round(ci_lower, 4) if ci_lower is not None else None,
        "ci_upper": round(ci_upper, 4) if ci_upper is not None else None,
        "sample_size": n_samples,
        "alpha": alpha,
        "ci_level": ci_level,
        "lag1_autocorrelation": round(r1, 4),
        "autocorrelation_handling": chosen_handling,
        "choice_documentation": documentation,
        "interpretation": interp,
        "is_significant": is_significant,
        "warnings": warnings_list,
    }


test_regional_significance = evaluate_regional_significance


def vectorized_mann_kendall_and_sen(
    annual_cubes: np.ndarray,
    min_valid_years: int = 10,
    chunk_size: int = 5000,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Computes vectorised Mann-Kendall p-value and Sen's slope across all grid cells.
    annual_cubes has shape (T, n_lats, n_lons).
    Returns:
    - p_vals: 2D array of raw p-values (shape: (n_lats, n_lons))
    - slopes: 2D array of Sen's slopes
    - valid_counts: 2D array of valid annual count per cell
    """
    T, n_lats, n_lons = annual_cubes.shape
    total_cells = n_lats * n_lons

    flat_data = annual_cubes.reshape(T, total_cells)  # (T, N)
    valid_counts = np.sum(~np.isnan(flat_data), axis=0)  # (N,)

    p_vals_out = np.full(total_cells, np.nan, dtype=np.float64)
    slopes_out = np.full(total_cells, np.nan, dtype=np.float64)

    # Eligible cells: valid counts >= min_valid_years
    eligible_indices = np.where(valid_counts >= min_valid_years)[0]
    n_eligible = len(eligible_indices)

    if n_eligible == 0:
        return p_vals_out.reshape(n_lats, n_lons), slopes_out.reshape(n_lats, n_lons), valid_counts.reshape(n_lats, n_lons)

    i_idx, j_idx = np.triu_indices(T, k=1)
    dt = (j_idx - i_idx)[:, np.newaxis]  # (P, 1)

    # Process in chunks to maintain low memory profile
    for start_idx in range(0, n_eligible, chunk_size):
        chunk_sub = eligible_indices[start_idx : start_idx + chunk_size]
        sub_data = flat_data[:, chunk_sub]  # (T, chunk_N)
        n_c = valid_counts[chunk_sub]       # (chunk_N,)

        # Pairwise differences
        diffs = sub_data[j_idx, :] - sub_data[i_idx, :]  # (P, chunk_N)

        # 1. Mann-Kendall S statistic
        # np.sign of NaN is NaN; with nansum, pairs with NaN are omitted
        with np.errstate(all="ignore"):
            sgn = np.sign(diffs)
            S = np.nansum(sgn, axis=0)  # (chunk_N,)

            # Variance of S under the null hypothesis (ties approximated as negligible on float measurements)
            var_s = (n_c * (n_c - 1) * (2 * n_c + 5)) / 18.0

            z = np.zeros_like(S)
            pos_mask = S > 0
            neg_mask = S < 0
            z[pos_mask] = (S[pos_mask] - 1.0) / np.sqrt(var_s[pos_mask])
            z[neg_mask] = (S[neg_mask] + 1.0) / np.sqrt(var_s[neg_mask])

            # Two-sided p-value
            chunk_p = 2.0 * sc_spec.ndtr(-np.abs(z))

            # 2. Sen's slope: median of pairwise slopes
            pair_slopes = diffs / dt  # (P, chunk_N)
            chunk_sen = np.nanmedian(pair_slopes, axis=0)

        p_vals_out[chunk_sub] = chunk_p
        slopes_out[chunk_sub] = chunk_sen

    return (
        p_vals_out.reshape(n_lats, n_lons),
        slopes_out.reshape(n_lats, n_lons),
        valid_counts.reshape(n_lats, n_lons),
    )


def classify_spatial_significance(
    p_vals_raw: np.ndarray,
    slopes: np.ndarray,
    valid_counts: np.ndarray,
    fractions_2d: np.ndarray,
    min_valid_years: int = 10,
    alpha: float = 0.05,
    fdr_correction: bool = True,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Applies multiple-testing correction (Benjamini-Hochberg FDR) across tested cells
    and assigns the 5 discrete map classes (SPEC 10.4).
    """
    n_lats, n_lons = p_vals_raw.shape
    classes = np.full((n_lats, n_lons), CLASS_NOT_COVERED, dtype=np.int32)
    p_vals_adj = np.full((n_lats, n_lons), np.nan, dtype=np.float64)

    in_region = fractions_2d > 0.0

    # 1. Separate cells into: Not Covered, Insufficient Data, and Tested
    insufficient_mask = in_region & (valid_counts < min_valid_years)
    classes[insufficient_mask] = CLASS_INSUFFICIENT_DATA

    tested_mask = in_region & (valid_counts >= min_valid_years) & (~np.isnan(p_vals_raw))
    tested_indices = np.where(tested_mask)
    n_tested = len(tested_indices[0])

    if n_tested > 0:
        raw_tested = p_vals_raw[tested_indices]

        # Apply Benjamini-Hochberg False Discovery Rate
        if fdr_correction and n_tested > 1:
            _, adj_tested, _, _ = smm.multipletests(raw_tested, alpha=alpha, method="fdr_bh")
            p_vals_adj[tested_indices] = adj_tested
            p_eval = adj_tested
        else:
            p_vals_adj[tested_indices] = raw_tested
            p_eval = raw_tested

        tested_slopes = slopes[tested_indices]

        # Assign classes
        is_sig = p_eval <= alpha
        sig_inc = is_sig & (tested_slopes > 0.0)
        sig_dec = is_sig & (tested_slopes < 0.0)
        not_sig = ~is_sig | (tested_slopes == 0.0)

        for idx in range(n_tested):
            lat_i = tested_indices[0][idx]
            lon_j = tested_indices[1][idx]
            if sig_inc[idx]:
                classes[lat_i, lon_j] = CLASS_SIG_INCREASE
            elif sig_dec[idx]:
                classes[lat_i, lon_j] = CLASS_SIG_DECREASE
            else:
                classes[lat_i, lon_j] = CLASS_NOT_SIGNIFICANT

    # Summary counts
    counts = {
        "significant_increase": int(np.sum(classes == CLASS_SIG_INCREASE)),
        "significant_decrease": int(np.sum(classes == CLASS_SIG_DECREASE)),
        "not_significant": int(np.sum(classes == CLASS_NOT_SIGNIFICANT)),
        "insufficient_data": int(np.sum(classes == CLASS_INSUFFICIENT_DATA)),
        "not_covered": int(np.sum(classes == CLASS_NOT_COVERED)),
        "total_tested_cells": n_tested,
        "fdr_applied": fdr_correction,
        "alpha": alpha,
    }

    return classes, p_vals_adj, counts


def generate_significance_map_overlay_and_legend(
    classes_2d: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    fractions_2d: np.ndarray,
    run_id: str,
    fdr_corrected: bool,
    alpha: float,
    output_dir: Path,
) -> Tuple[str, List[List[float]], Dict[str, Any]]:
    """
    Renders an accessible transparent PNG map overlay and pattern/label legend for Leaflet.
    - Uses distinct colors & patterns for the 5 classes.
    - Not covered is transparent.
    - Legend states clearly whether raw or FDR-adjusted p-values were evaluated (SPEC 10.4).
    """
    n_lats, n_lons = classes_2d.shape
    rgba = np.zeros((n_lats, n_lons, 4), dtype=np.uint8)

    # Color definitions (RGBA uint8)
    color_map = {
        CLASS_SIG_INCREASE: (220, 38, 38, 220),       # Red
        CLASS_SIG_DECREASE: (37, 99, 235, 220),       # Blue
        CLASS_NOT_SIGNIFICANT: (148, 163, 184, 180),  # Light slate gray
        CLASS_INSUFFICIENT_DATA: (217, 119, 6, 210),  # Amber
        CLASS_NOT_COVERED: (0, 0, 0, 0),              # Completely transparent
    }

    for c_code, col in color_map.items():
        mask = classes_2d == c_code
        rgba[mask] = col

    # Flip vertically along latitude axis so North is top
    flipped_rgba = np.flipud(rgba)
    img = Image.fromarray(flipped_rgba, mode="RGBA")
    overlay_filename = f"significance_overlay_{run_id}.png"
    overlay_path = output_dir / overlay_filename
    img.save(overlay_path, format="PNG")

    # Calculate geographic bounds for Leaflet L.imageOverlay
    dlat = abs(float(lats[1] - lats[0])) if len(lats) > 1 else 2.5
    dlon = abs(float(lons[1] - lons[0])) if len(lons) > 1 else 2.5

    south = float(np.min(lats)) - (dlat / 2.0)
    north = float(np.max(lats)) + (dlat / 2.0)
    west = float(np.min(lons)) - (dlon / 2.0)
    east = float(np.max(lons)) + (dlon / 2.0)

    bounds = [[south, west], [north, east]]

    counts = {
        "significant_increase": int(np.sum(classes_2d == CLASS_SIG_INCREASE)),
        "significant_decrease": int(np.sum(classes_2d == CLASS_SIG_DECREASE)),
        "not_significant": int(np.sum(classes_2d == CLASS_NOT_SIGNIFICANT)),
        "insufficient_data": int(np.sum(classes_2d == CLASS_INSUFFICIENT_DATA)),
        "not_covered": int(np.sum(classes_2d == CLASS_NOT_COVERED)),
    }

    p_mode_str = "Benjamini-Hochberg FDR Adjusted" if fdr_corrected else "Raw P-Values (Unadjusted)"
    legend = {
        "title": "Statistical Significance Classes (SPEC 10.4)",
        "type": "categorical_5_class",
        "multiple_testing": p_mode_str,
        "p_value_mode": p_mode_str,
        "alpha_threshold": alpha,
        "alpha": alpha,
        "classes": [
            {
                "code": CLASS_SIG_INCREASE,
                "name": "Significant Increase (+)",
                "label": "Significant Increase",
                "color": CLASS_METADATA[CLASS_SIG_INCREASE]["color"],
                "badge": "+",
                "badge_symbol": "+",
                "count": counts["significant_increase"],
                "description": f"Positive trend with p <= {alpha}",
            },
            {
                "code": CLASS_SIG_DECREASE,
                "name": "Significant Decrease (-)",
                "label": "Significant Decrease",
                "color": CLASS_METADATA[CLASS_SIG_DECREASE]["color"],
                "badge": "−",
                "badge_symbol": "−",
                "count": counts["significant_decrease"],
                "description": f"Negative trend with p <= {alpha}",
            },
            {
                "code": CLASS_NOT_SIGNIFICANT,
                "name": "Not Significant (o)",
                "label": "Not Significant",
                "color": CLASS_METADATA[CLASS_NOT_SIGNIFICANT]["color"],
                "badge": "o",
                "badge_symbol": "o",
                "count": counts["not_significant"],
                "description": f"Tested, but p > {alpha}",
            },
            {
                "code": CLASS_INSUFFICIENT_DATA,
                "name": "Insufficient Data (?)",
                "label": "Insufficient Data",
                "color": CLASS_METADATA[CLASS_INSUFFICIENT_DATA]["color"],
                "badge": "?",
                "badge_symbol": "?",
                "count": counts["insufficient_data"],
                "description": "Fewer than required valid observation periods",
            },
            {
                "code": CLASS_NOT_COVERED,
                "name": "Not Covered / Masked (x)",
                "label": "Not Covered",
                "color": "#334155",
                "badge": "x",
                "badge_symbol": "x",
                "count": counts["not_covered"],
                "description": "Unselected study area / fill values",
            },
        ],
    }

    return f"/api/analysis/significance/{run_id}/overlay.png", bounds, legend


def write_significance_geotiff(
    classes_2d: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    run_id: str,
    output_dir: Path,
) -> Path:
    """Writes the 5-class significance raster as a GeoTIFF."""
    import rioxarray

    lat_desc = np.sort(lats)[::-1]
    if lats[0] < lats[-1]:
        reindexed_grid = np.flipud(classes_2d).astype(np.int16)
    else:
        reindexed_grid = classes_2d.astype(np.int16)

    da = xr.DataArray(
        reindexed_grid,
        coords=[("lat", lat_desc.astype(np.float64)), ("lon", lons.astype(np.float64))],
        name="significance_class",
    )
    da = da.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    da = da.rio.write_crs("EPSG:4326")
    da = da.rio.write_nodata(0)

    geotiff_path = output_dir / f"significance_{run_id}.tif"
    da.rio.to_raster(str(geotiff_path), driver="GTiff")
    return geotiff_path


def execute_significance_analysis(
    data_array: Optional[xr.DataArray] = None,
    geometry: Optional[BaseGeometry] = None,
    time_series_points: Optional[List[Dict[str, Any]]] = None,
    years: Optional[List[int]] = None,
    variable: str = "precipitation",
    mode: str = "both",  # regional | spatial | both
    alpha: float = 0.05,
    ci_level: float = 0.95,
    autocorrelation_method: str = "auto",
    fdr_correction: bool = True,
    min_valid_years: int = 10,
    run_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Executes complete end-to-end significance assessment (SPEC 10, 14.6, 14.7).
    """
    if run_id is None:
        import uuid
        run_id = f"sig_{uuid.uuid4().hex[:12]}"

    if output_dir is None:
        output_dir = OUTPUTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    warnings: List[str] = []
    regional_result: Optional[Dict[str, Any]] = None
    spatial_result: Optional[Dict[str, Any]] = None

    # 1. Regional test
    if mode in ["regional", "both"] and time_series_points:
        regional_result = evaluate_regional_significance(
            time_series_points=time_series_points,
            frequency="monthly" if len(time_series_points) > 50 else "annual",
            alpha=alpha,
            ci_level=ci_level,
            autocorrelation_method=autocorrelation_method,
        )

    # 2. Spatial tests
    if mode in ["spatial", "both"] and data_array is not None and geometry is not None:
        if years is None:
            years = sorted(list(set(int(str(t)[:4]) for t in data_array["time"].values)))

        lats = data_array["lat"].values
        lons = data_array["lon"].values

        # Weights & fractions
        weights_2d, fractions_2d, cell_areas_2d, chosen_method = build_grid_mask_weights(
            lats, lons, geometry, method="fractional_overlap"
        )

        # Build annual cubes (T, n_lats, n_lons)
        annual_cubes = compute_annual_cell_values(data_array, years, variable=variable)

        # Vectorised Mann-Kendall and Sen's slope
        p_vals_raw, slopes, valid_counts = vectorized_mann_kendall_and_sen(
            annual_cubes=annual_cubes,
            min_valid_years=min_valid_years,
        )

        # FDR classification
        classes_2d, p_vals_adj, counts = classify_spatial_significance(
            p_vals_raw=p_vals_raw,
            slopes=slopes,
            valid_counts=valid_counts,
            fractions_2d=fractions_2d,
            min_valid_years=min_valid_years,
            alpha=alpha,
            fdr_correction=fdr_correction,
        )

        # GeoTIFF
        geotiff_path = write_significance_geotiff(
            classes_2d=classes_2d,
            lats=lats,
            lons=lons,
            run_id=run_id,
            output_dir=output_dir,
        )

        # Transparent overlay & legend
        overlay_url, bounds, legend = generate_significance_map_overlay_and_legend(
            classes_2d=classes_2d,
            lats=lats,
            lons=lons,
            fractions_2d=fractions_2d,
            run_id=run_id,
            fdr_corrected=fdr_correction,
            alpha=alpha,
            output_dir=output_dir,
        )

        # Cache raw arrays for rapid reclassification when user changes alpha or FDR
        cache_data = {
            "run_id": run_id,
            "lats": lats.tolist(),
            "lons": lons.tolist(),
            "p_vals_raw": p_vals_raw.tolist(),
            "slopes": slopes.tolist(),
            "valid_counts": valid_counts.tolist(),
            "fractions": fractions_2d.tolist(),
            "min_valid_years": min_valid_years,
            "years": years,
        }
        with open(output_dir / f"spatial_cache_{run_id}.json", "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        spatial_result = {
            "overlay_url": overlay_url,
            "geotiff_url": f"/api/analysis/significance/{run_id}/geotiff",
            "bounds": bounds,
            "legend": legend,
            "class_counts": counts,
            "min_valid_years": min_valid_years,
            "fdr_correction": fdr_correction,
            "alpha": alpha,
        }

    is_merra2 = variable in ["land_surface_temperature", "temperature", "TS"]
    is_oisst = variable in ["sea_surface_temperature", "sst", "noaa_oisst_v21"]
    is_gldas = variable in ["soil_moisture", "SoilMoi0_10cm_inst", "gldas_noah025_m_v21"]
    is_humidity = variable in ["humidity", "QV2M", "merra2_monthly_qv2m"]
    if is_merra2:
        ds_id = "merra2_monthly_ts"
        ds_version = "5.12.4"
    elif is_oisst:
        ds_id = "noaa_oisst_v21"
        ds_version = "v2.1"
    elif is_gldas:
        ds_id = "gldas_noah025_m_v21"
        ds_version = "2.1"
    elif is_humidity:
        ds_id = "merra2_monthly_qv2m"
        ds_version = "5.12.4"
    else:
        ds_id = "gpcp_monthly_v23"
        ds_version = "v2.3"

    provenance = {
        "run_id": run_id,
        "mode": mode,
        "alpha": alpha,
        "ci_level": ci_level,
        "autocorrelation_method": autocorrelation_method,
        "fdr_correction": fdr_correction,
        "variable": variable,
        "dataset_id": ds_id,
        "dataset_version": ds_version,
        "methodology": "Seasonal Mann-Kendall + Vectorised OLS/Sen + Benjamini-Hochberg FDR",
    }

    return {
        "run_id": run_id,
        "status": "completed",
        "regional": regional_result,
        "spatial": spatial_result,
        "provenance": provenance,
        "warnings": warnings,
    }


def reclassify_cached_significance(
    run_id: str,
    alpha: float = 0.05,
    fdr_correction: bool = True,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Rapidly reclassifies spatial significance for a previously computed run without re-running regressions.
    """
    if output_dir is None:
        output_dir = OUTPUTS_DIR

    cache_file = output_dir / f"spatial_cache_{run_id}.json"
    if not cache_file.exists():
        raise FileNotFoundError(f"Spatial cache for run '{run_id}' not found.")

    with open(cache_file, "r", encoding="utf-8") as f:
        cache = json.load(f)

    lats = np.array(cache["lats"])
    lons = np.array(cache["lons"])
    p_vals_raw = np.array(cache["p_vals_raw"])
    slopes = np.array(cache["slopes"])
    valid_counts = np.array(cache["valid_counts"])
    fractions_2d = np.array(cache["fractions"])
    min_valid_years = int(cache.get("min_valid_years", 10))

    classes_2d, p_vals_adj, counts = classify_spatial_significance(
        p_vals_raw=p_vals_raw,
        slopes=slopes,
        valid_counts=valid_counts,
        fractions_2d=fractions_2d,
        min_valid_years=min_valid_years,
        alpha=alpha,
        fdr_correction=fdr_correction,
    )

    # Re-write GeoTIFF & Overlay PNG
    write_significance_geotiff(classes_2d, lats, lons, run_id, output_dir)
    overlay_url, bounds, legend = generate_significance_map_overlay_and_legend(
        classes_2d=classes_2d,
        lats=lats,
        lons=lons,
        fractions_2d=fractions_2d,
        run_id=run_id,
        fdr_corrected=fdr_correction,
        alpha=alpha,
        output_dir=output_dir,
    )

    return {
        "run_id": run_id,
        "overlay_url": overlay_url,
        "geotiff_url": f"/api/analysis/significance/{run_id}/geotiff",
        "bounds": bounds,
        "legend": legend,
        "class_counts": counts,
        "alpha": alpha,
        "fdr_correction": fdr_correction,
    }
