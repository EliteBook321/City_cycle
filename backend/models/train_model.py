"""Chronological training pipeline for the UCI Bike Sharing hour.csv dataset."""
import json
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
from backend.config import DATASET_PATH, MODEL_ARTIFACT_PATH, MODEL_INFO_PATH, METRICS_PATH, RANDOM_SEED

FEATURES = ["yr", "season", "mnth", "hr", "holiday", "weekday", "workingday", "weathersit", "temp", "atemp", "hum", "windspeed"]
TARGET = "cnt"


def chronological_split(frame: pd.DataFrame, train_fraction: float = 0.8):
    """Split a chronologically sorted frame without shuffling future observations."""
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be strictly between 0 and 1")
    ordered = frame.sort_values("timestamp").reset_index(drop=True)
    split_at = int(len(ordered) * train_fraction)
    if split_at == 0 or split_at == len(ordered):
        raise ValueError("Both chronological partitions must contain at least one row")
    return ordered.iloc[:split_at], ordered.iloc[split_at:]


def evaluate_values(actual, predicted) -> dict:
    """Return errors in the target's original unit: rentals per hour."""
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
    }


def train(dataset_path: Path = DATASET_PATH) -> dict:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found at {dataset_path}. Download the UCI Bike Sharing Dataset and place hour.csv in backend/data/.")
    frame = pd.read_csv(dataset_path)
    required = set(FEATURES + [TARGET, "dteday"])
    absent = sorted(required - set(frame.columns))
    if absent:
        raise ValueError(f"Dataset is missing required columns: {', '.join(absent)}")
    if frame[FEATURES + [TARGET]].isna().any().any():
        raise ValueError("Dataset has missing required feature/target values; resolve them before training.")
    for column in FEATURES + [TARGET]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise ValueError(f"Dataset column {column!r} contains non-numeric values.")
    bounds = {"yr": (0, 1), "season": (1, 4), "mnth": (1, 12), "hr": (0, 23), "holiday": (0, 1), "weekday": (0, 6), "workingday": (0, 1), "weathersit": (1, 4), "temp": (0, 1), "atemp": (0, 1), "hum": (0, 1), "windspeed": (0, 1), TARGET: (0, None)}
    for column, (lower, upper) in bounds.items():
        invalid = frame[column].lt(lower) | (frame[column].gt(upper) if upper is not None else False)
        if invalid.any():
            raise ValueError(f"Dataset column {column!r} contains values outside the expected range.")
    frame["timestamp"] = pd.to_datetime(frame["dteday"], errors="coerce") + pd.to_timedelta(frame["hr"], unit="h")
    if frame["timestamp"].isna().any():
        raise ValueError("Dataset contains unparseable dteday values.")
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    if len(frame) < 20:
        raise ValueError("At least 20 valid hourly observations are required for chronological evaluation.")
    train_frame, test_frame = chronological_split(frame)
    X_train, X_test = train_frame[FEATURES], test_frame[FEATURES]
    y_train, y_test = train_frame[TARGET], test_frame[TARGET]
    train_mean = float(y_train.mean())
    timestamp_to_count = frame.set_index("timestamp")[TARGET]
    last_week = test_frame["timestamp"] - pd.Timedelta(days=7)
    weekly_values = last_week.map(timestamp_to_count).fillna(train_mean)
    baselines = [
        {"model_name": "Training mean baseline", **evaluate_values(y_test, np.full(len(y_test), train_mean)), "baseline": True},
        {"model_name": "Same hour last week", **evaluate_values(y_test, weekly_values), "baseline": True, "fallback": "training mean when prior-week observation is unavailable"},
    ]
    candidates = {
        "Linear Regression": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LinearRegression()),
        "Random Forest": make_pipeline(SimpleImputer(strategy="median"), RandomForestRegressor(n_estimators=240, min_samples_leaf=2, max_features=0.85, n_jobs=-1, random_state=RANDOM_SEED)),
        "Gradient Boosting": make_pipeline(SimpleImputer(strategy="median"), GradientBoostingRegressor(n_estimators=150, learning_rate=0.05, max_depth=2, random_state=RANDOM_SEED)),
    }
    comparison = list(baselines)
    fitted = {}
    for name, estimator in candidates.items():
        estimator.fit(X_train, y_train)
        prediction = estimator.predict(X_test)
        result = {"model_name": name, **evaluate_values(y_test, prediction), "baseline": False}
        comparison.append(result)
        fitted[name] = estimator
    winner = min((item for item in comparison if not item["baseline"]), key=lambda item: (item["mae"], item["rmse"]))
    selected = fitted[winner["model_name"]]
    final_predictions = selected.predict(X_test)
    final_estimator = selected.steps[-1][1]
    importance_values = getattr(final_estimator, "feature_importances_", None)
    if importance_values is None and hasattr(final_estimator, "coef_"):
        scaler = selected.steps[-2][1]
        importance_values = np.abs(final_estimator.coef_ / scaler.scale_)
    feature_importance = []
    if importance_values is not None and len(importance_values) == len(FEATURES):
        total_importance = float(np.sum(importance_values)) or 1.0
        feature_importance = sorted(
            [{"feature": name, "importance": float(value / total_importance)} for name, value in zip(FEATURES, importance_values)],
            key=lambda item: item["importance"], reverse=True,
        )
    MODEL_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected, MODEL_ARTIFACT_PATH)
    trained_at = datetime.now(timezone.utc).isoformat()
    dataset_hash = sha256(dataset_path.read_bytes()).hexdigest()
    sample_indices = np.linspace(0, len(test_frame) - 1, min(160, len(test_frame)), dtype=int)
    test_series = [{"timestamp": test_frame.iloc[index]["timestamp"].isoformat(), "actual": float(y_test.iloc[index]), "predicted": float(final_predictions[index]), "residual": float(y_test.iloc[index] - final_predictions[index])} for index in sample_indices]
    baseline_mae = baselines[0]["mae"]
    metrics = {"evaluated": True, "selected_model": winner["model_name"], "mae": winner["mae"], "rmse": winner["rmse"], "r2": float(selected.score(X_test, y_test)), "comparison": comparison, "baselines": baselines, "feature_importance": feature_importance, "selected_beats_mean_baseline": winner["mae"] < baseline_mae, "mae_improvement_vs_mean_baseline_pct": float((1 - winner["mae"] / baseline_mae) * 100) if baseline_mae else None, "test_series": test_series, "train_period": {"start": str(train_frame["timestamp"].min()), "end": str(train_frame["timestamp"].max()), "rows": len(train_frame)}, "test_period": {"start": str(test_frame["timestamp"].min()), "end": str(test_frame["timestamp"].max()), "rows": len(test_frame)}, "trained_at": trained_at, "target": TARGET, "dataset_rows": len(frame), "missing_values": int(frame.isna().sum().sum()), "error_unit": "rentals per hour"}
    info = {"model_name": winner["model_name"], "model_version": "1.0.0", "features": FEATURES, "trained_at": trained_at, "target": TARGET, "dataset_rows": len(frame), "dataset_sha256": dataset_hash, "train_period": metrics["train_period"], "test_period": metrics["test_period"], "feature_importance": feature_importance}
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    MODEL_INFO_PATH.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    summary = train()
    print(json.dumps({key: value for key, value in summary.items() if key != "test_series"}, indent=2))
