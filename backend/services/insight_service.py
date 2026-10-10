"""Data-derived historical summaries; no hardcoded demand claims."""
import calendar as month_calendar
from datetime import date
import pandas as pd
from backend.config import DATASET_PATH
from backend.models.model_loader import load_model


def season_for_month(month: int) -> int:
    """Map calendar month to the UCI Bike Sharing season category."""
    if not 1 <= month <= 12:
        raise ValueError("month must be in range 1..12")
    return (month - 1) // 3 + 1


def get_month_calendar(year: int, month: int) -> dict:
    """Return daily aggregate rentals for one source-data month (not reservations)."""
    if month < 1 or month > 12:
        raise ValueError("month must be in range 1..12")
    if year < 2011 or year > 2012:
        return {"available": False, "year": year, "month": month, "days": [], "message": "The source dataset only covers 2011 to 2012; there are no daily booking records for this month."}
    if not DATASET_PATH.exists():
        return {"available": False, "year": year, "month": month, "days": [], "message": "Historical daily totals are unavailable until hour.csv is installed."}
    frame = pd.read_csv(DATASET_PATH)
    needed = {"dteday", "hr", "cnt"}
    if not needed.issubset(frame.columns):
        return {"available": False, "year": year, "month": month, "days": [], "message": "Dataset is missing date, hour, or rental-count columns."}
    dates = pd.to_datetime(frame["dteday"], errors="coerce")
    frame["cnt"] = pd.to_numeric(frame["cnt"], errors="coerce")
    frame["hr"] = pd.to_numeric(frame["hr"], errors="coerce")
    frame = frame.assign(calendar_date=dates).dropna(subset=["calendar_date", "cnt", "hr"])
    frame = frame[(frame["calendar_date"].dt.year == year) & (frame["calendar_date"].dt.month == month)]
    grouped = frame.groupby(frame["calendar_date"].dt.day)
    days = []
    for day_number, observations in grouped:
        hourly = observations.groupby("hr")["cnt"].sum()
        days.append({
            "day": int(day_number),
            "rentals": int(observations["cnt"].sum()),
            "hours_recorded": int(observations["hr"].nunique()),
            "peak_hour": int(hourly.idxmax()),
            "peak_hour_rentals": int(hourly.max()),
        })
    return {
        "available": bool(days),
        "year": year,
        "month": month,
        "month_name": month_calendar.month_name[month],
        "days_in_month": month_calendar.monthrange(year, month)[1],
        "weekday_offset": date(year, month, 1).weekday(),
        "days": days,
        "total_rentals": sum(item["rentals"] for item in days),
        "message": None if days else "No observations are present for this month in hour.csv.",
        "metric_name": "aggregate hourly rentals per day; not advance reservations or individual bookings",
    }


def get_date_range_summary(start_date: date, end_date: date) -> dict:
    """Aggregate authentic hourly counts into daily totals for an inclusive range."""
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    if (end_date - start_date).days > 730:
        raise ValueError("Select a date range of 731 days or less")
    if not DATASET_PATH.exists():
        return {"available": False, "message": "Historical range analysis requires the original hour.csv dataset."}
    frame = pd.read_csv(DATASET_PATH)
    required = {"dteday", "hr", "cnt"}
    if not required.issubset(frame.columns):
        return {"available": False, "message": "Dataset is missing date, hour, or rental-count columns."}
    dates = pd.to_datetime(frame["dteday"], errors="coerce")
    frame["cnt"] = pd.to_numeric(frame["cnt"], errors="coerce")
    frame["hr"] = pd.to_numeric(frame["hr"], errors="coerce")
    frame = frame.assign(calendar_date=dates.dt.date).dropna(subset=["calendar_date", "cnt", "hr"])
    selected = frame[(frame["calendar_date"] >= start_date) & (frame["calendar_date"] <= end_date)]
    if selected.empty:
        return {"available": False, "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "daily": [], "message": "No historical observations exist within this range. The dataset covers 2011-01-01 through 2012-12-31."}
    grouped = selected.groupby("calendar_date")
    daily = []
    for current_date, observations in grouped:
        hourly = observations.groupby("hr")["cnt"].sum()
        daily.append({
            "date": current_date.isoformat(),
            "rentals": int(observations["cnt"].sum()),
            "hours_recorded": int(observations["hr"].nunique()),
            "peak_hour": int(hourly.idxmax()),
            "peak_hour_rentals": int(hourly.max()),
        })
    daily_values = [item["rentals"] for item in daily]
    weekday_means = {}
    if "workingday" in selected:
        for is_working, label in ((1, "working_days"), (0, "non_working_days")):
            row_dates = selected[selected["workingday"] == is_working].groupby("calendar_date")["cnt"].sum()
            if not row_dates.empty:
                weekday_means[label] = round(float(row_dates.mean()), 1)
    top_features = []
    for feature, label in (("hr", "hour of day"), ("weathersit", "weather category"), ("temp", "normalized temperature"), ("workingday", "working-day status"), ("season", "season")):
        if feature in selected and selected[feature].nunique() > 1:
            grouped_feature = selected.groupby(feature)["cnt"].mean()
            top_features.append({"feature": label, "low_category_mean": round(float(grouped_feature.min()), 1), "high_category_mean": round(float(grouped_feature.max()), 1), "category_spread": round(float(grouped_feature.max() - grouped_feature.min()), 1)})
    top_features.sort(key=lambda item: item["category_spread"], reverse=True)
    return {
        "available": True,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "source_period": {"start": str(selected["calendar_date"].min()), "end": str(selected["calendar_date"].max())},
        "days_with_data": len(daily),
        "hourly_rows": int(len(selected)),
        "total_rentals": int(sum(daily_values)),
        "average_daily_rentals": round(sum(daily_values) / len(daily_values), 1),
        "peak_day": max(daily, key=lambda item: item["rentals"]),
        "daily": daily,
        "workingday_daily_averages": weekday_means,
        "largest_observed_category_spreads": top_features[:3],
        "metric_name": "completed historical rentals aggregated by date; not reservations or live bookings",
    }


def get_insights() -> dict:
    path = DATASET_PATH
    if not path.exists():
        return {"available": False, "message": "Insights unavailable until the original hour.csv dataset is installed.", "summaries": {}}
    try:
        frame = pd.read_csv(path)
        needed = {"hr", "cnt"}
        if not needed.issubset(frame.columns):
            return {"available": False, "message": "Dataset is missing required hr and cnt columns.", "summaries": {}}
        if frame.empty:
            return {"available": False, "message": "Dataset has no observations to summarize.", "summaries": {}}
        frame["hr"] = pd.to_numeric(frame["hr"], errors="coerce")
        frame["cnt"] = pd.to_numeric(frame["cnt"], errors="coerce")
        if frame[["hr", "cnt"]].isna().any().any():
            return {"available": False, "message": "Dataset contains missing or non-numeric hour/target values; insights cannot be calculated reliably.", "summaries": {}}
        hourly = frame.groupby("hr")["cnt"].mean().reindex(range(24)).round(1)
        observed_hours = hourly.dropna()
        if observed_hours.empty:
            return {"available": False, "message": "Dataset has no valid hourly demand observations.", "summaries": {}}
        result = {"available": True, "row_count": int(len(frame)), "missing_values": int(frame.isna().sum().sum()), "total_rentals": int(frame["cnt"].sum()), "hourly_average": [{"hour": int(hour), "rentals": None if pd.isna(value) else float(value)} for hour, value in hourly.items()], "summaries": {"peak_hour": int(observed_hours.idxmax()), "peak_hour_average": float(observed_hours.max()), "mean_hourly_rentals": round(float(frame["cnt"].mean()), 1)}}
        if "dteday" in frame:
            data_dates = pd.to_datetime(frame["dteday"], errors="coerce").dropna()
            if not data_dates.empty:
                result["data_period"] = {"start": data_dates.min().date().isoformat(), "end": data_dates.max().date().isoformat()}
        for column, label in (("weekday", "weekday"), ("season", "season"), ("weathersit", "weather")):
            if column in frame:
                grouped = frame.groupby(column)["cnt"].mean().round(1)
                result["summaries"][f"{label}_average"] = {str(key): float(value) for key, value in grouped.items()}
        if "weekday" in frame:
            weekend = frame[frame["weekday"].isin([0, 6])]["cnt"]
            weekday = frame[~frame["weekday"].isin([0, 6])]["cnt"]
            result["summaries"]["weekday_weekend_average"] = {
                "weekdays": round(float(weekday.mean()), 1) if not weekday.empty else None,
                "weekends": round(float(weekend.mean()), 1) if not weekend.empty else None,
            }
        workday_hourly = []
        if "workingday" in frame:
            regime_means = frame.groupby(["workingday", "hr"])["cnt"].mean()
            for hour in range(24):
                workday_hourly.append({
                    "hour": hour,
                    "workingday": round(float(regime_means.get((1, hour), 0)), 1),
                    "weekend_or_nonworking": round(float(regime_means.get((0, hour), 0)), 1),
                })
        result["hourly_by_regime"] = workday_hourly
        if workday_hourly:
            morning = max((item for item in workday_hourly if 5 <= item["hour"] <= 11), key=lambda item: item["workingday"])
            evening = max((item for item in workday_hourly if 14 <= item["hour"] <= 20), key=lambda item: item["workingday"])
            weekend_peak = max(workday_hourly, key=lambda item: item["weekend_or_nonworking"])
            result["summaries"]["workday_morning_peak"] = {"hour": morning["hour"], "average": morning["workingday"]}
            result["summaries"]["workday_evening_peak"] = {"hour": evening["hour"], "average": evening["workingday"]}
            result["summaries"]["nonworking_peak"] = {"hour": weekend_peak["hour"], "average": weekend_peak["weekend_or_nonworking"]}
        if "dteday" in frame:
            dates = pd.to_datetime(frame["dteday"], errors="coerce")
            year_means = frame.assign(calendar_year=dates.dt.year).groupby("calendar_year")["cnt"].mean().round(1)
            result["summaries"]["yearly_average"] = {str(year): float(value) for year, value in year_means.items() if pd.notna(year)}
            if len(year_means) >= 2:
                first, last = year_means.iloc[0], year_means.iloc[-1]
                result["summaries"]["year_over_year_change_pct"] = round(float((last - first) / first * 100), 1) if first else None
        if "temp" in frame:
            numeric_temp = pd.to_numeric(frame["temp"], errors="coerce")
            bands = pd.qcut(numeric_temp, q=4, duplicates="drop")
            band_means = frame.assign(temp_band=bands).groupby("temp_band", observed=True)["cnt"].agg(["mean", "count"])
            result["summaries"]["temperature_bands"] = [
                {"range": str(interval), "average_rentals": round(float(row["mean"]), 1), "rows": int(row["count"])}
                for interval, row in band_means.iterrows()
            ]
            result["summaries"]["temperature_band_average"] = {
                str(interval): round(float(row["mean"]), 1)
                for interval, row in band_means.iterrows()
            }
        try:
            model = load_model()
            estimator = model.steps[-1][1] if model is not None and hasattr(model, "steps") else model
            importances = getattr(estimator, "feature_importances_", None)
            if importances is None and hasattr(estimator, "coef_") and model is not None and hasattr(model, "steps"):
                scaler = model.steps[-2][1]
                importances = abs(estimator.coef_ / scaler.scale_)
            if importances is not None:
                from backend.models.model_loader import load_metadata
                features = load_metadata().get("features", [])
                if len(features) == len(importances):
                    importance_total = float(sum(abs(float(value)) for value in importances)) or 1.0
                    result["feature_importance"] = sorted(
                        [{"feature": name, "importance": float(abs(float(value)) / importance_total)} for name, value in zip(features, importances)],
                        key=lambda item: item["importance"], reverse=True,
                    )
        except Exception:
            # Historical summaries remain available even if an optional model artifact is invalid.
            pass
        result["ops_guidance"] = _build_ops_guidance(frame, result)
        return result
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        return {"available": False, "message": f"Could not read dataset: {exc}", "summaries": {}}


def _build_ops_guidance(frame: pd.DataFrame, result: dict) -> list[dict]:
    """Build measured, non-causal operating prompts from historical patterns."""
    summaries = result["summaries"]
    guidance = []
    morning = summaries.get("workday_morning_peak")
    evening = summaries.get("workday_evening_peak")
    if morning and evening:
        guidance.append({
            "title": "Plan around measured workday peaks",
            "evidence": f"Observed workday peaks: {morning['hour']:02d}:00 ({morning['average']:,.1f} mean rentals/hour) and {evening['hour']:02d}:00 ({evening['average']:,.1f}).",
            "action": "Schedule staffing and any citywide rebalancing review before those windows; station-specific routes require station inventory data.",
        })
    regimes = summaries.get("weekday_weekend_average", {})
    if regimes.get("weekdays") is not None and regimes.get("weekends") is not None:
        guidance.append({
            "title": "Use separate working-day and non-working-day plans",
            "evidence": f"Observed means: {regimes['weekdays']:,.1f} rentals/hour on weekdays and {regimes['weekends']:,.1f} on weekend days.",
            "action": "Review staffing profiles by day regime rather than applying one schedule across the week.",
        })
    weather = summaries.get("weather_average", {})
    clear = weather.get("1")
    wet_records = frame[pd.to_numeric(frame["weathersit"], errors="coerce").isin([2, 3, 4])]["cnt"] if "weathersit" in frame else pd.Series(dtype=float)
    if clear is not None and not wet_records.empty:
        wet_average = float(wet_records.mean())
        guidance.append({
            "title": "Use weather as a planning signal",
            "evidence": f"Historical clear-category average: {clear:,.1f}; mean of observed non-clear categories: {wet_average:,.1f} rentals/hour.",
            "action": "Check forecast weather when adjusting staffing; these are associations and do not establish causation.",
        })
    return guidance[:3]
