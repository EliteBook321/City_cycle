"""Evaluation metadata and chronological model-training helpers."""
import json
from pathlib import Path
from backend.config import METRICS_PATH


def get_metrics() -> dict:
    if not METRICS_PATH.exists():
        return {"evaluated": False, "message": "Not evaluated. Train a model with the real Bike Sharing dataset."}
    try:
        return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"evaluated": False, "message": "Evaluation metadata is unavailable or invalid."}


def regression_metrics(actual, predicted) -> dict:
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    return {"mae": float(mean_absolute_error(actual, predicted)), "rmse": float(mean_squared_error(actual, predicted) ** 0.5)}
