"""Inference service using the exact feature contract persisted at training."""
import pandas as pd
from datetime import date
from backend.models.model_loader import load_model, load_metadata
from backend.schemas.forecast_schema import ForecastInput


def predict(payload: ForecastInput) -> dict:
    try:
        model = load_model()
    except Exception as exc:
        raise RuntimeError("The saved model artifact could not be loaded. Retrain the model and restart the API.") from exc
    metadata = load_metadata()
    if model is None:
        raise RuntimeError("No trained model is available. Add backend/data/hour.csv and run python -m backend.models.train_model.")
    features = metadata.get("features", [])
    if not features:
        raise RuntimeError("Model metadata is incomplete. Retrain the model using the documented training command.")
    # The public API uses readable field names; training persists the UCI column names.
    api_values = payload.model_dump()
    aliases = {
        "yr": "year",
        "mnth": "month",
        "hr": "hour",
        "weathersit": "weather",
        "temp": "temperature",
        "atemp": "feels_like",
        "hum": "humidity",
    }
    values = {name: api_values.get(aliases.get(name, name)) for name in features}
    missing = [name for name, value in values.items() if value is None]
    if missing:
        raise RuntimeError(f"Forecast feature contract mismatch: {', '.join(missing)}")
    inference_frame = pd.DataFrame([{name: values[name] for name in features}], columns=features)
    raw_prediction = max(0.0, float(model.predict(inference_frame)[0]))
    prediction = max(0, int(round(raw_prediction)))
    return {"predicted_rentals": prediction, "predicted_rentals_unrounded": round(raw_prediction, 3), "model_name": metadata.get("model_name", "Unknown"), "model_version": metadata.get("model_version", "unversioned"), "estimate_note": "Citywide hourly estimate from historical patterns; not station-level availability or a guaranteed outcome."}


def predict_today(target_date: date | None = None) -> dict:
    """Forecast each hour today using typical historical weather for this month.

    Weather is a historical scenario, not a live observation or weather forecast.
    The year feature uses the dataset's latest year (2012) because 2026 is outside
    the source period and the model was not trained on contemporary records.
    """
    import pandas as pd
    from backend.config import DATASET_PATH
    from backend.schemas.forecast_schema import ForecastInput
    from backend.services.insight_service import season_for_month

    target_date = target_date or date.today()
    if not DATASET_PATH.exists():
        raise RuntimeError("Source dataset is missing. Install the original hour.csv and train the model first.")
    frame = pd.read_csv(DATASET_PATH)
    if not {"mnth", "workingday", "weathersit", "temp", "atemp", "hum", "windspeed"}.issubset(frame.columns):
        raise RuntimeError("Dataset lacks calendar/weather fields required for an all-day scenario.")
    weekday = target_date.weekday()
    dataset_weekday = (weekday + 1) % 7  # UCI: Sunday=0; Python: Monday=0.
    workingday = int(dataset_weekday not in (0, 6))
    reference = frame[(frame["mnth"] == target_date.month) & (frame["workingday"] == workingday)]
    if reference.empty:
        reference = frame[frame["mnth"] == target_date.month]
    if reference.empty:
        reference = frame
    typical = {
        "weather": int(reference["weathersit"].mode().iloc[0]),
        "temperature": float(reference["temp"].median()),
        "feels_like": float(reference["atemp"].median()),
        "humidity": float(reference["hum"].median()),
        "windspeed": float(reference["windspeed"].median()),
    }
    day_frame = frame[frame["workingday"] == workingday] if "workingday" in frame.columns else frame
    hourly_history = day_frame.groupby("hr")["cnt"].mean()
    predictions = []
    for hour in range(24):
        payload = ForecastInput(
            year=1,
            season=season_for_month(target_date.month),
            month=target_date.month,
            hour=hour,
            weekday=dataset_weekday,
            workingday=workingday,
            **typical,
        )
        estimate = predict(payload)["predicted_rentals"]
        predictions.append({"hour": hour, "predicted_rentals": estimate})
    from backend.services.evaluation_service import get_metrics
    metrics = get_metrics()
    residuals = [item["residual"] for item in metrics.get("test_series", []) if isinstance(item.get("residual"), (int, float))]
    residual_limits = pd.Series(residuals).quantile([0.05, 0.95]) if residuals else None
    if residual_limits is not None:
        lower_error, upper_error = float(residual_limits.iloc[0]), float(residual_limits.iloc[1])
        predictions = [
            {**item, "lower_bound": max(0, int(round(item["predicted_rentals"] + lower_error))), "upper_bound": max(0, int(round(item["predicted_rentals"] + upper_error)))}
            for item in predictions
        ]
    peak = max(predictions, key=lambda item: item["predicted_rentals"])
    elevated_threshold = float(hourly_history.quantile(0.75))
    elevated = [item for item in predictions if item["predicted_rentals"] >= elevated_threshold]
    elevated_hours = [item["hour"] for item in elevated]
    elevated_windows = []
    for hour in elevated_hours:
        if elevated_windows and hour == elevated_windows[-1][1] + 1:
            elevated_windows[-1][1] = hour
        else:
            elevated_windows.append([hour, hour])
    elevated_periods = [
        f"{start:02d}:00" if start == end else f"{start:02d}:00–{end:02d}:00"
        for start, end in elevated_windows
    ]
    return {
        "forecast_date": target_date.isoformat(),
        "weekday": target_date.strftime("%A"),
        "month": target_date.month,
        "weekday_index": dataset_weekday,
        "workingday": workingday,
        "predictions": predictions,
        "peak_hour": peak["hour"],
        "peak_demand": peak["predicted_rentals"],
        "total_predicted_rentals": sum(item["predicted_rentals"] for item in predictions),
        "recommended_ops_threshold": round(elevated_threshold, 1),
        "uncertainty_note": "Optional range uses the 5th to 95th percentiles of sampled chronological holdout residuals. It is descriptive, not a calibrated or guaranteed interval." if residual_limits is not None else "No holdout residual sample is available for an estimate range.",
        "historical_high_demand_threshold": round(elevated_threshold, 1),
        "elevated_hours": elevated_hours,
        "elevated_periods": elevated_periods,
        "operational_suggestions": [
            {
                "title": "Review staffing before elevated hours",
                "detail": f"The scenario reaches the historical 75th-percentile guide during {', '.join(elevated_periods) or 'no hours'}. Consider a staff readiness check before these windows.",
                "priority": "HIGH" if peak["predicted_rentals"] >= elevated_threshold * 1.35 else "MEDIUM",
            },
            {
                "title": "Plan a citywide rebalancing review",
                "detail": f"Review system-level capacity ahead of the estimated {peak['hour']:02d}:00 peak. Station-level inventory is not in this dataset, so exact bike or dock moves cannot be calculated.",
                "priority": "HIGH" if peak["predicted_rentals"] >= elevated_threshold * 1.35 else "MEDIUM",
            },
        ],
        "weather_scenario": "Typical historical weather for this month and day type; not a live weather forecast.",
        "weather_context": {
            "label": f"Typical month profile · category {typical['weather']}",
            "note": "Historical median weather inputs; no live weather service is connected.",
            **typical,
        },
        "model_name": load_metadata().get("model_name", "Unknown"),
        "model_version": load_metadata().get("model_version", "unversioned"),
        "data_period": "2011–2012 historical data",
        "estimate_note": "Illustrative citywide scenario for today using the latest year category in the historical dataset. The source ends in 2012; this is not a validated 2026 forecast or station-level availability.",
    }
