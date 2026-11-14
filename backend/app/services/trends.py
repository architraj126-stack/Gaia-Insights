"""
Trend Analysis Service (SPEC Section 8, 14.6, and Scientific Non-Negotiables).

Statistical methods:
- Ordinary Least Squares (OLS) linear regression: slope, intercept, p-value, r-squared, std_err,
  and analytical regression confidence band from the model itself.
- Non-parametric Theil-Sen estimator (Sen's slope) with confidence interval.
- Non-parametric Mann-Kendall test for monotonic trend.
- Seasonal Mann-Kendall test (grouped by month/season).
- Modified autocorrelation-aware Mann-Kendall test (Hamed and Rao 1998 approach via pymannkendall).
- Moving average smoothing (centered, displaying window size).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pymannkendall as pmk
from scipy import stats

from backend.app.config import settings

logger = logging.getLogger("backend.services.trends")


def parse_date_to_decimal_year(date_str: str) -> float:
    """
    Converts YYYY-MM-DD or YYYY-MM or YYYY string into continuous decimal year.
    For monthly data: Jan -> Y + 0.5/12, Dec -> Y + 11.5/12.
    """
    parts = date_str.split("-")
    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else 1
    return year + (month - 0.5) / 12.0


def compute_ols_regression(
    x_valid: np.ndarray,
    y_valid: np.ndarray,
    x_all: np.ndarray,
    alpha: float = 0.05,
) -> Tuple[Dict[str, Any], np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculates OLS linear regression and exact regression confidence band.

    Confidence band formula (Working-Hotelling / pointwise confidence band for E[Y|X=x0]):
        SE(x0) = s_e * sqrt(1/n + (x0 - x_bar)^2 / S_xx)
        CI(x0) = y_hat(x0) +/- t_{alpha/2, n-2} * SE(x0)
    Derived strictly from the regression itself, never an arbitrary +/- offset.
    """
    n = len(x_valid)
    if n < 3:
        empty_arr = np.full(len(x_all), np.nan)
        return {
            "slope_per_year": None,
            "intercept": None,
            "p_value": None,
            "r_squared": None,
            "std_err": None,
            "ci_lower_slope": None,
            "ci_upper_slope": None,
            "trend_direction": "insufficient data",
        }, empty_arr, empty_arr, empty_arr

    x_mean = float(np.mean(x_valid))
    Sxx = float(np.sum((x_valid - x_mean) ** 2))

    res = stats.linregress(x_valid, y_valid)
    slope = float(res.slope)
    intercept = float(res.intercept)
    p_value = float(res.pvalue)
    r_squared = float(res.rvalue ** 2)
    std_err = float(res.stderr) if res.stderr is not None else 0.0

    df = n - 2
    if df > 0 and Sxx > 0:
        y_pred_valid = slope * x_valid + intercept
        residuals = y_valid - y_pred_valid
        s_e = float(np.sqrt(np.sum(residuals ** 2) / df))
        t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df))
        ci_lower_slope = slope - t_crit * std_err
        ci_upper_slope = slope + t_crit * std_err

        # Compute regression line and band across all points
        fitted_line = slope * x_all + intercept
        se_band = s_e * np.sqrt((1.0 / n) + ((x_all - x_mean) ** 2) / Sxx)
        ci_lower = fitted_line - t_crit * se_band
        ci_upper = fitted_line + t_crit * se_band
    else:
        fitted_line = slope * x_all + intercept
        ci_lower = fitted_line
        ci_upper = fitted_line
        ci_lower_slope = slope
        ci_upper_slope = slope

    if p_value < alpha:
        direction = "increasing" if slope > 0 else "decreasing"
    else:
        direction = "no clear trend"

    stats_dict = {
        "slope_per_year": round(slope, 5),
        "intercept": round(intercept, 5),
        "p_value": round(p_value, 6),
        "r_squared": round(r_squared, 4),
        "std_err": round(std_err, 5),
        "ci_lower_slope": round(float(ci_lower_slope), 5),
        "ci_upper_slope": round(float(ci_upper_slope), 5),
        "trend_direction": direction,
    }

    return stats_dict, fitted_line, ci_lower, ci_upper


def compute_sens_slope(
    x_valid: np.ndarray,
    y_valid: np.ndarray,
    x_all: np.ndarray,
    alpha: float = 0.05,
) -> Tuple[Dict[str, Any], np.ndarray]:
    """
    Computes Theil-Sen estimator with non-parametric confidence interval via scipy.stats.theilslopes.
    """
    n = len(x_valid)
    if n < 3:
        empty_arr = np.full(len(x_all), np.nan)
        return {
            "slope_per_year": None,
            "intercept": None,
            "ci_lower": None,
            "ci_upper": None,
            "confidence_level": 1.0 - alpha,
            "trend_direction": "insufficient data",
        }, empty_arr

    res = stats.theilslopes(y_valid, x_valid, alpha=1.0 - alpha, method="separate")
    slope = float(res.slope)
    intercept = float(res.intercept)
    ci_lower = float(res.low_slope)
    ci_upper = float(res.high_slope)

    # If confidence interval excludes zero, trend is significant
    if ci_lower > 0:
        direction = "increasing"
    elif ci_upper < 0:
        direction = "decreasing"
    else:
        direction = "no clear trend"

    sens_line = intercept + slope * x_all

    stats_dict = {
        "slope_per_year": round(slope, 5),
        "intercept": round(intercept, 5),
        "ci_lower": round(ci_lower, 5),
        "ci_upper": round(ci_upper, 5),
        "confidence_level": round(1.0 - alpha, 2),
        "trend_direction": direction,
    }

    return stats_dict, sens_line


def compute_mann_kendall_tests(
    y_valid: np.ndarray,
    y_all_with_nans: List[Optional[float]],
    aggregation: str = "monthly",
    alpha: float = 0.05,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Runs:
    1. Plain Mann-Kendall test (original_test)
    2. Seasonal Mann-Kendall test (seasonal_test with period=12 for monthly, 4 for seasonal)
    3. Modified autocorrelation-aware Mann-Kendall test (Hamed-Rao approach)
    """
    n = len(y_valid)
    if n < 4:
        empty_mk = {
            "trend": "insufficient data",
            "p_value": None,
            "z": None,
            "tau": None,
            "s": None,
            "var_s": None,
            "significant": False,
        }
        return empty_mk, None, empty_mk

    # 1. Plain Mann-Kendall
    try:
        mk_res = pmk.original_test(y_valid, alpha=alpha)
        mk_dict = {
            "trend": "increasing" if mk_res.trend == "increasing" else "decreasing" if mk_res.trend == "decreasing" else "no clear trend",
            "p_value": round(float(mk_res.p), 6),
            "z": round(float(mk_res.z), 4),
            "tau": round(float(mk_res.Tau), 4),
            "s": round(float(mk_res.s), 2),
            "var_s": round(float(mk_res.var_s), 2),
            "significant": bool(mk_res.h),
        }
    except Exception as e:
        logger.warning("Plain Mann-Kendall failed: %s", e)
        mk_dict = {
            "trend": "error",
            "p_value": None,
            "z": None,
            "tau": None,
            "s": None,
            "var_s": None,
            "significant": False,
        }

    # 2. Seasonal Mann-Kendall
    smk_dict: Optional[Dict[str, Any]] = None
    period = 12 if aggregation == "monthly" else 4 if aggregation == "seasonal" else None
    if period and len(y_all_with_nans) >= period * 2:
        try:
            # pymannkendall handles np.nan in seasonal_test
            y_arr = np.array([np.nan if v is None else float(v) for v in y_all_with_nans])
            smk_res = pmk.seasonal_test(y_arr, period=period, alpha=alpha)
            smk_dict = {
                "trend": "increasing" if smk_res.trend == "increasing" else "decreasing" if smk_res.trend == "decreasing" else "no clear trend",
                "p_value": round(float(smk_res.p), 6),
                "z": round(float(smk_res.z), 4),
                "tau": round(float(smk_res.Tau), 4),
                "s": round(float(smk_res.s), 2),
                "var_s": round(float(smk_res.var_s), 2),
                "significant": bool(smk_res.h),
                "period": period,
            }
        except Exception as e:
            logger.warning("Seasonal Mann-Kendall failed: %s", e)
            smk_dict = None

    # 3. Modified Mann-Kendall (Hamed & Rao autocorrelation-aware)
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            mod_res = pmk.hamed_rao_modification_test(y_valid, alpha=alpha)

        p_val = round(float(mod_res.p), 6) if mod_res.p is not None and not np.isnan(mod_res.p) else None
        z_val = round(float(mod_res.z), 4) if mod_res.z is not None and not np.isnan(mod_res.z) else None
        tau_val = round(float(mod_res.Tau), 4) if mod_res.Tau is not None and not np.isnan(mod_res.Tau) else None
        s_val = round(float(mod_res.s), 2) if mod_res.s is not None and not np.isnan(mod_res.s) else None
        var_s_val = round(float(mod_res.var_s), 2) if mod_res.var_s is not None and not np.isnan(mod_res.var_s) else None

        mod_dict = {
            "trend": "increasing" if mod_res.trend == "increasing" else "decreasing" if mod_res.trend == "decreasing" else "no clear trend",
            "p_value": p_val,
            "z": z_val,
            "tau": tau_val,
            "s": s_val,
            "var_s": var_s_val,
            "significant": bool(mod_res.h) if mod_res.h is not None else False,
            "method": "hamed_rao",
        }
    except Exception as e:
        logger.warning("Modified Mann-Kendall failed: %s", e)
        mod_dict = {
            "trend": "error",
            "p_value": None,
            "z": None,
            "tau": None,
            "s": None,
            "var_s": None,
            "significant": False,
            "method": "hamed_rao",
        }

    return mk_dict, smk_dict, mod_dict


def compute_moving_average(
    values: List[Optional[float]],
    window: int = 12,
) -> List[Optional[float]]:
    """
    Calculates centered moving average with window length, preserving data structure.
    """
    if len(values) == 0:
        return []
    s = pd.Series([np.nan if v is None else float(v) for v in values])
    min_periods = max(1, window // 2)
    ma_series = s.rolling(window=window, center=True, min_periods=min_periods).mean()
    out: List[Optional[float]] = []
    for val in ma_series:
        if pd.isna(val):
            out.append(None)
        else:
            out.append(round(float(val), 4))
    return out


def analyze_timeseries_trends(
    points: List[Dict[str, Any]],
    aggregation: str = "monthly",
    variable: str = "precipitation",
    alpha: Optional[float] = None,
    min_data_points: Optional[int] = None,
    moving_avg_window: Optional[int] = None,
    expected_total_steps: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Orchestrates full trend analysis for time-series points.
    Enriches each point with fitted OLS, CI band, Sen's slope line, and moving average.
    Returns:
        (enriched_points, summary_metrics)
    """
    if alpha is None:
        alpha = settings.TREND_ALPHA
    if min_data_points is None:
        min_data_points = settings.TREND_MIN_DATA_POINTS

    # Determine default moving average window if not provided
    if moving_avg_window is None:
        if aggregation == "monthly":
            moving_avg_window = 12
        elif aggregation == "seasonal":
            moving_avg_window = 4
        else:
            moving_avg_window = 5

    total_n = len(points)
    if total_n == 0:
        empty_summary = {
            "trend_direction": "insufficient data",
            "slope_method_displayed": "OLS regression",
            "rate_of_change": None,
            "rate_of_change_units": "native/year",
            "mean": None,
            "estimated_total_change": None,
            "elapsed_years": 0.0,
            "valid_n": 0,
            "expected_n": expected_total_steps or 0,
            "completeness": {
                "valid": 0,
                "expected": expected_total_steps or 0,
                "pct": 0.0,
                "denominator_description": f"Expected {expected_total_steps or 0} steps",
            },
            "ols": {},
            "sens_slope": {},
            "mann_kendall": {},
            "seasonal_mann_kendall": None,
            "modified_mann_kendall": {},
            "alpha": alpha,
            "min_data_points": min_data_points,
            "moving_average_window": moving_avg_window,
        }
        return points, empty_summary

    # Extract coordinate arrays
    x_all = np.array([parse_date_to_decimal_year(p["date"]) for p in points])
    raw_vals = [p.get("value") for p in points]

    valid_indices = [
        i for i, p in enumerate(points)
        if p.get("value") is not None and not p.get("is_missing")
    ]
    valid_n = len(valid_indices)
    expected_n = expected_total_steps if expected_total_steps is not None else total_n

    completeness_pct = round((valid_n / expected_n * 100.0), 2) if expected_n > 0 else 0.0
    denom_desc = f"Expected {expected_n} intervals from {points[0]['date']} to {points[-1]['date']}"

    # Moving average
    ma_values = compute_moving_average(raw_vals, window=moving_avg_window)

    # Check minimum data rule
    if valid_n < min_data_points:
        logger.info("Insufficient valid data points (%d < %d)", valid_n, min_data_points)
        enriched_points = []
        for i, pt in enumerate(points):
            p_copy = dict(pt)
            p_copy["fitted_ols"] = None
            p_copy["ols_ci_lower"] = None
            p_copy["ols_ci_upper"] = None
            p_copy["sens_line"] = None
            p_copy["moving_avg"] = ma_values[i]
            enriched_points.append(p_copy)

        valid_vals_list = [float(points[i]["value"]) for i in valid_indices]
        mean_val = round(float(np.mean(valid_vals_list)), 4) if valid_vals_list else None

        summary = {
            "trend_direction": "insufficient data",
            "slope_method_displayed": "OLS regression",
            "rate_of_change": None,
            "rate_of_change_units": f"{points[0].get('units', 'native')}/year",
            "mean": mean_val,
            "estimated_total_change": None,
            "elapsed_years": round(float(x_all[-1] - x_all[0]), 2) if len(x_all) > 1 else 0.0,
            "valid_n": valid_n,
            "expected_n": expected_n,
            "completeness": {
                "valid": valid_n,
                "expected": expected_n,
                "pct": completeness_pct,
                "denominator_description": denom_desc,
            },
            "ols": {
                "slope_per_year": None,
                "intercept": None,
                "p_value": None,
                "r_squared": None,
                "std_err": None,
                "ci_lower_slope": None,
                "ci_upper_slope": None,
                "trend_direction": "insufficient data",
            },
            "sens_slope": {
                "slope_per_year": None,
                "intercept": None,
                "ci_lower": None,
                "ci_upper": None,
                "confidence_level": 1.0 - alpha,
                "trend_direction": "insufficient data",
            },
            "mann_kendall": {
                "trend": "insufficient data",
                "p_value": None,
                "z": None,
                "tau": None,
                "s": None,
                "var_s": None,
                "significant": False,
            },
            "seasonal_mann_kendall": None,
            "modified_mann_kendall": {
                "trend": "insufficient data",
                "p_value": None,
                "z": None,
                "tau": None,
                "s": None,
                "var_s": None,
                "significant": False,
                "method": "hamed_rao",
            },
            "alpha": alpha,
            "min_data_points": min_data_points,
            "moving_average_window": moving_avg_window,
        }
        return enriched_points, summary

    x_valid = x_all[valid_indices]
    y_valid = np.array([float(points[i]["value"]) for i in valid_indices])

    # 1. OLS regression & confidence band
    ols_dict, fitted_ols_arr, ols_ci_lower_arr, ols_ci_upper_arr = compute_ols_regression(
        x_valid, y_valid, x_all, alpha=alpha
    )

    # 2. Sen's slope
    sens_dict, sens_line_arr = compute_sens_slope(
        x_valid, y_valid, x_all, alpha=alpha
    )

    # 3. Mann-Kendall tests
    mk_dict, smk_dict, mod_dict = compute_mann_kendall_tests(
        y_valid, raw_vals, aggregation=aggregation, alpha=alpha
    )

    # Enrich points
    enriched_points = []
    for i, pt in enumerate(points):
        p_copy = dict(pt)
        p_copy["fitted_ols"] = round(float(fitted_ols_arr[i]), 4) if not np.isnan(fitted_ols_arr[i]) else None
        p_copy["ols_ci_lower"] = round(float(ols_ci_lower_arr[i]), 4) if not np.isnan(ols_ci_lower_arr[i]) else None
        p_copy["ols_ci_upper"] = round(float(ols_ci_upper_arr[i]), 4) if not np.isnan(ols_ci_upper_arr[i]) else None
        p_copy["sens_line"] = round(float(sens_line_arr[i]), 4) if not np.isnan(sens_line_arr[i]) else None
        p_copy["moving_avg"] = ma_values[i]
        enriched_points.append(p_copy)

    # General metrics
    mean_val = round(float(np.mean(y_valid)), 4)
    elapsed_years = round(float(x_all[-1] - x_all[0]), 2) if len(x_all) > 1 else 1.0
    slope_val = ols_dict.get("slope_per_year")
    est_total_change = round(slope_val * elapsed_years, 4) if slope_val is not None else None

    # Trend direction priority:
    # Uses alpha and minimum data rule from config.
    overall_direction = ols_dict.get("trend_direction", "no clear trend")

    units_str = points[0].get("units", "native")

    summary = {
        "trend_direction": overall_direction,
        "slope_method_displayed": "linear_regression",
        "rate_of_change": slope_val,
        "rate_of_change_units": f"{units_str}/year",
        "mean": mean_val,
        "estimated_total_change": est_total_change,
        "elapsed_years": elapsed_years,
        "valid_n": valid_n,
        "expected_n": expected_n,
        "completeness": {
            "valid": valid_n,
            "expected": expected_n,
            "pct": completeness_pct,
            "denominator_description": denom_desc,
        },
        "ols": ols_dict,
        "sens_slope": sens_dict,
        "mann_kendall": mk_dict,
        "seasonal_mann_kendall": smk_dict,
        "modified_mann_kendall": mod_dict,
        "alpha": alpha,
        "min_data_points": min_data_points,
        "moving_average_window": moving_avg_window,
    }

    return enriched_points, summary
