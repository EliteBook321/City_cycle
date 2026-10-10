from backend.schemas.forecast_schema import ForecastInput
from backend.services.evaluation_service import regression_metrics
from backend.services.prediction_service import predict
from backend.models.train_model import FEATURES, chronological_split
import pandas as pd
import pytest


def sample_payload():
    return ForecastInput(season=2, month=6, hour=8, weekday=1, temperature=0.5, feels_like=0.5, humidity=0.6, windspeed=0.2)


def test_forecast_input_bounds():
    with pytest.raises(ValueError):
        ForecastInput(season=5, month=6, hour=8, weekday=1, temperature=0.5, feels_like=0.5, humidity=0.6, windspeed=0.2)


def test_missing_model_returns_clear_error(monkeypatch):
    monkeypatch.setattr("backend.services.prediction_service.load_model", lambda: None)
    with pytest.raises(RuntimeError, match="No trained model"):
        predict(sample_payload())


def test_prediction_output_is_nonnegative_integer(monkeypatch):
    class FakeModel:
        def predict(self, values):
            return [-4.3]
    monkeypatch.setattr("backend.services.prediction_service.load_model", lambda: FakeModel())
    monkeypatch.setattr("backend.services.prediction_service.load_metadata", lambda: {"features": ["hour"], "model_name": "Test", "model_version": "test"})
    result = predict(sample_payload())
    assert result["predicted_rentals"] == 0
    assert isinstance(result["predicted_rentals"], int)


def test_prediction_maps_api_names_to_training_feature_names(monkeypatch):
    class FakeModel:
        def predict(self, rows):
            assert rows.iloc[0].tolist() == [1, 2, 6, 8, 0, 1, 1, 1, 0.5, 0.5, 0.6, 0.2]
            return [125.0]

    features = ["yr", "season", "mnth", "hr", "holiday", "weekday", "workingday", "weathersit", "temp", "atemp", "hum", "windspeed"]
    monkeypatch.setattr("backend.services.prediction_service.load_model", lambda: FakeModel())
    monkeypatch.setattr("backend.services.prediction_service.load_metadata", lambda: {"features": features, "model_name": "Test", "model_version": "test"})
    assert predict(sample_payload())["predicted_rentals"] == 125


def test_mae_rmse_are_calculated():
    assert regression_metrics([1, 3], [2, 1]) == {"mae": 1.5, "rmse": pytest.approx(1.5811388300841898)}


def test_target_leaking_columns_are_not_features():
    assert "casual" not in FEATURES
    assert "registered" not in FEATURES
    assert "cnt" not in FEATURES


def test_chronological_split_sorts_and_keeps_later_holdout():
    frame = pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-03", "2024-01-01", "2024-01-02"]), "value": [3, 1, 2]})
    train, test = chronological_split(frame, train_fraction=2 / 3)
    assert train["value"].tolist() == [1, 2]
    assert test["value"].tolist() == [3]


def test_training_pipeline_writes_evaluation_to_temporary_artifacts(tmp_path, monkeypatch):
    from backend.models import train_model

    timestamps = pd.date_range("2024-01-01", periods=48, freq="h")
    frame = pd.DataFrame({
        "dteday": timestamps.strftime("%Y-%m-%d"),
        "yr": 0, "season": 1, "mnth": timestamps.month, "hr": timestamps.hour,
        "holiday": 0, "weekday": timestamps.dayofweek, "workingday": 1,
        "weathersit": 1, "temp": 0.4, "atemp": 0.4, "hum": 0.5,
        "windspeed": 0.2, "casual": 9000, "registered": 12000,
        "cnt": timestamps.hour * 5 + 10,
    })
    dataset_path = tmp_path / "fixture-hour.csv"
    frame.to_csv(dataset_path, index=False)
    monkeypatch.setattr(train_model, "MODEL_ARTIFACT_PATH", tmp_path / "model.joblib")
    monkeypatch.setattr(train_model, "METRICS_PATH", tmp_path / "metrics.json")
    monkeypatch.setattr(train_model, "MODEL_INFO_PATH", tmp_path / "model_info.json")

    metrics = train_model.train(dataset_path)

    assert metrics["evaluated"] is True
    assert metrics["train_period"]["end"] < metrics["test_period"]["start"]
    assert metrics["test_series"] and {"actual", "predicted", "residual"}.issubset(metrics["test_series"][0])
    assert {"Training mean baseline", "Same hour last week"}.issubset({item["model_name"] for item in metrics["baselines"]})
    assert metrics["mae"] < next(item["mae"] for item in metrics["baselines"] if item["model_name"] == "Training mean baseline")
    assert (tmp_path / "model.joblib").exists()
    assert (tmp_path / "metrics.json").exists()
    assert "casual" not in train_model.FEATURES
    assert "registered" not in train_model.FEATURES


def test_today_scenario_generates_24_hours_with_historical_weather_note(tmp_path, monkeypatch):
    from datetime import date
    from backend.services import prediction_service

    dataset = pd.DataFrame({
        "mnth": [10, 10], "workingday": [0, 1], "weathersit": [2, 1],
        "temp": [0.4, 0.6], "atemp": [0.4, 0.6], "hum": [0.7, 0.5],
        "windspeed": [0.2, 0.1], "hr": [8, 8], "cnt": [250, 400],
    })
    path = tmp_path / "hour.csv"
    dataset.to_csv(path, index=False)
    monkeypatch.setattr("backend.config.DATASET_PATH", path)
    monkeypatch.setattr(prediction_service, "predict", lambda payload: {"predicted_rentals": 100 + payload.hour})

    result = prediction_service.predict_today(date(2026, 10, 10))

    assert len(result["predictions"]) == 24
    assert result["weekday"] == "Saturday"
    assert result["workingday"] == 0
    assert result["weather_context"]["weather"] == 2
    assert "not a live weather forecast" in result["weather_scenario"]
    assert result["peak_hour"] == 23
    assert result["predictions"][0]["predicted_rentals"] == 100
