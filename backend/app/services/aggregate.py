"""
Temporal Aggregation Service (SPEC 14.3, Scientific Rule 7).

Scientific aggregation rules:
- Precipitation rate (mm/day) -> monthly accumulation (mm):
    multiply rate by the exact number of calendar days in each month (handling leap years).
- Annual accumulation (mm):
    sum of all 12 valid months. If any month is missing or NaN, annual total is NaN with an
    incomplete flag.
- Seasonal accumulation (mm):
    - DJF: Dec (prior year) + Jan (target year) + Feb (target year)
    - MAM: Mar + Apr + May (target year)
    - JJA: Jun + Jul + Aug (target year)
    - SON: Sep + Oct + Nov (target year)
    Requires all 3 seasonal months to be valid; otherwise NaN with an incomplete flag.
"""
from __future__ import annotations

import calendar
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


def get_days_in_month(year: int, month: int) -> int:
    """Returns exact number of days in the given month, accurately accounting for leap years."""
    return calendar.monthrange(year, month)[1]


def kelvin_to_celsius(k: Any) -> Any:
    """
    Converts temperature in Kelvin to degrees Celsius (°C = K - 273.15).
    SPEC 14.4 Temperature conversion rule.
    """
    if k is None:
        return None
    if isinstance(k, np.ndarray):
        return np.round(k.astype(np.float64) - 273.15, 4)
    if isinstance(k, (list, tuple)):
        return [kelvin_to_celsius(x) for x in k]
    if isinstance(k, (float, np.floating)) and np.isnan(k):
        return np.nan
    return round(float(k) - 273.15, 4)


def rate_to_monthly_accumulation(rate_mm_day: Optional[float], year: int, month: int) -> Optional[float]:
    """
    Converts daily precipitation rate (mm/day) to monthly total (mm)
    by multiplying by days in the month. Returns None if rate is None.
    """
    if rate_mm_day is None:
        return None
    days = get_days_in_month(year, month)
    return round(rate_mm_day * days, 4)


def aggregate_monthly(
    time_steps: List[str],
    mean_rates: List[Optional[float]],
    valid_counts: List[int],
    valid_areas: List[float],
    variable: str = "precipitation",
) -> List[Dict[str, Any]]:
    """
    Produces monthly aggregated time-series points.
    For precipitation, adds monthly accumulated total in mm.
    """
    points: List[Dict[str, Any]] = []

    for t_str, rate, count, area in zip(time_steps, mean_rates, valid_counts, valid_areas):
        dt_parts = t_str.split("-")
        year = int(dt_parts[0])
        month = int(dt_parts[1])

        is_missing = (rate is None) or (count == 0)

        if variable == "precipitation":
            accum_val = rate_to_monthly_accumulation(rate, year, month)
            points.append({
                "date": t_str,
                "value": accum_val,  # monthly accumulation in mm
                "units": "mm",
                "rate_mm_day": rate,
                "native_units": "mm/day",
                "valid_cell_count": count,
                "valid_area_km2": area,
                "is_missing": is_missing,
                "flags": ["missing_data"] if is_missing else [],
            })
        elif variable in ["land_surface_temperature", "temperature"]:
            val_celsius = kelvin_to_celsius(rate) if rate is not None else None
            points.append({
                "date": t_str,
                "value": val_celsius,
                "units": "°C",
                "native_value": rate,
                "native_units": "K",
                "valid_cell_count": count,
                "valid_area_km2": area,
                "is_missing": is_missing,
                "flags": ["missing_data"] if is_missing else [],
            })
        elif variable in ["sea_surface_temperature", "sst", "noaa_oisst_v21"]:
            points.append({
                "date": t_str,
                "value": rate,
                "units": "°C",
                "native_value": rate,
                "native_units": "degC",
                "valid_cell_count": count,
                "valid_area_km2": area,
                "is_missing": is_missing,
                "flags": ["missing_data"] if is_missing else [],
            })
        elif variable in ["soil_moisture", "SoilMoi0_10cm_inst", "gldas_noah025_m_v21"]:
            points.append({
                "date": t_str,
                "value": rate,
                "units": "kg/m²",
                "native_value": rate,
                "native_units": "kg m-2",
                "valid_cell_count": count,
                "valid_area_km2": area,
                "is_missing": is_missing,
                "flags": ["missing_data"] if is_missing else [],
            })
        elif variable in ["humidity", "QV2M", "merra2_monthly_qv2m"]:
            val_g_kg = (rate * 1000.0) if rate is not None else None
            points.append({
                "date": t_str,
                "value": val_g_kg,
                "units": "g/kg",
                "native_value": rate,
                "native_units": "kg kg-1",
                "valid_cell_count": count,
                "valid_area_km2": area,
                "is_missing": is_missing,
                "flags": ["missing_data"] if is_missing else [],
            })
        else:
            # Temperature or state variables: mean
            points.append({
                "date": t_str,
                "value": rate,
                "units": "native",
                "valid_cell_count": count,
                "valid_area_km2": area,
                "is_missing": is_missing,
                "flags": ["missing_data"] if is_missing else [],
            })

    return points


def aggregate_annual(
    monthly_points: List[Dict[str, Any]],
    variable: str = "precipitation",
) -> List[Dict[str, Any]]:
    """
    Aggregates monthly series to annual totals (or means).
    Annual total requires all 12 calendar months to be valid; otherwise NaN with incomplete flag.
    """
    # Group by year
    by_year: Dict[int, Dict[int, Dict[str, Any]]] = {}
    for pt in monthly_points:
        dt_parts = pt["date"].split("-")
        year = int(dt_parts[0])
        month = int(dt_parts[1])
        if year not in by_year:
            by_year[year] = {}
        by_year[year][month] = pt

    annual_points: List[Dict[str, Any]] = []

    for year in sorted(by_year.keys()):
        months_dict = by_year[year]
        missing_months = []
        valid_values = []
        counts = []
        areas = []

        for m in range(1, 13):
            m_pt = months_dict.get(m)
            if m_pt is None or m_pt["is_missing"] or m_pt["value"] is None:
                missing_months.append(m)
            else:
                valid_values.append(m_pt["value"])
                counts.append(m_pt.get("valid_cell_count") if m_pt.get("valid_cell_count") is not None else m_pt.get("valid_cells", 0))
                areas.append(m_pt.get("valid_area_km2", 0.0))

        is_complete = (len(missing_months) == 0) and (len(valid_values) == 12)
        is_temp = variable.lower() in [
            "land_surface_temperature",
            "temperature",
            "merra2_monthly_ts",
            "ts",
            "sea_surface_temperature",
            "noaa_oisst_v21",
            "sst",
        ]
        is_sm = variable.lower() in [
            "soil_moisture",
            "soilmoi0_10cm_inst",
            "gldas_noah025_m_v21",
        ]
        is_humidity = variable.lower() in [
            "humidity",
            "qv2m",
            "merra2_monthly_qv2m",
        ]
        is_state = is_temp or is_sm or is_humidity
        is_precip = variable.lower() in ["precipitation", "precip"]

        if is_complete:
            annual_val = (
                round(sum(valid_values) / 12.0, 4)
                if is_state
                else round(sum(valid_values), 4)
            )
            flags: List[str] = []
        else:
            annual_val = None
            flags = [f"incomplete_year (missing months: {missing_months})"]

        units_str = "mm" if is_precip else ("°C" if is_temp else ("kg/m²" if is_sm else ("g/kg" if is_humidity else "native")))
        annual_points.append({
            "date": f"{year}-01-01",
            "year": year,
            "value": annual_val,
            "units": units_str,
            "valid_months_count": len(valid_values),
            "missing_months": missing_months,
            "valid_cell_count": int(np.mean(counts)) if counts else 0,
            "valid_area_km2": round(float(np.mean(areas)), 2) if areas else 0.0,
            "is_missing": not is_complete,
            "flags": flags,
        })

    return annual_points


def aggregate_seasonal(
    monthly_points: List[Dict[str, Any]],
    variable: str = "precipitation",
) -> List[Dict[str, Any]]:
    """
    Aggregates monthly series into standard climatological seasons:
    - DJF: Dec (prior year), Jan (target year), Feb (target year)
    - MAM: Mar, Apr, May (target year)
    - JJA: Jun, Jul, Aug (target year)
    - SON: Sep, Oct, Nov (target year)

    Requires all 3 months of the season to be valid; otherwise NaN with incomplete flag.
    """
    # Index by (year, month)
    by_ym: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for pt in monthly_points:
        dt_parts = pt["date"].split("-")
        y = int(dt_parts[0])
        m = int(dt_parts[1])
        by_ym[(y, m)] = pt

    years = sorted(list(set(k[0] for k in by_ym.keys())))
    seasonal_points: List[Dict[str, Any]] = []

    season_defs = [
        ("DJF", lambda y: [(y - 1, 12), (y, 1), (y, 2)], "-01-01"),
        ("MAM", lambda y: [(y, 3), (y, 4), (y, 5)], "-04-01"),
        ("JJA", lambda y: [(y, 6), (y, 7), (y, 8)], "-07-01"),
        ("SON", lambda y: [(y, 9), (y, 10), (y, 11)], "-10-01"),
    ]

    for year in years:
        for season_name, ym_getter, season_date_suffix in season_defs:
            required_ym = ym_getter(year)
            missing = []
            vals = []
            counts = []
            areas = []

            for ym in required_ym:
                pt = by_ym.get(ym)
                if pt is None or pt["is_missing"] or pt["value"] is None:
                    missing.append(ym)
                else:
                    vals.append(pt["value"])
                    counts.append(pt["valid_cell_count"])
                    areas.append(pt["valid_area_km2"])

            is_complete = (len(missing) == 0) and (len(vals) == 3)
            is_temp = variable.lower() in [
                "land_surface_temperature",
                "temperature",
                "merra2_monthly_ts",
                "ts",
                "sea_surface_temperature",
                "noaa_oisst_v21",
                "sst",
            ]
            is_sm = variable.lower() in [
                "soil_moisture",
                "soilmoi0_10cm_inst",
                "gldas_noah025_m_v21",
            ]
            is_humidity = variable.lower() in [
                "humidity",
                "qv2m",
                "merra2_monthly_qv2m",
            ]
            is_state = is_temp or is_sm or is_humidity
            is_precip = variable.lower() in ["precipitation", "precip"]

            if is_complete:
                season_val = (
                    round(sum(vals) / 3.0, 4)
                    if is_state
                    else round(sum(vals), 4)
                )
                flags: List[str] = []
            else:
                season_val = None
                flags = [f"incomplete_season (missing: {missing})"]

            units_str = "mm" if is_precip else ("°C" if is_temp else ("kg/m²" if is_sm else ("g/kg" if is_humidity else "native")))
            seasonal_points.append({
                "date": f"{year}{season_date_suffix}",
                "season": season_name,
                "year": year,
                "value": season_val,
                "units": units_str,
                "valid_months_count": len(vals),
                "valid_cell_count": int(np.mean(counts)) if counts else 0,
                "valid_area_km2": round(float(np.mean(areas)), 2) if areas else 0.0,
                "is_missing": not is_complete,
                "flags": flags,
            })

    return seasonal_points
