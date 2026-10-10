from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "model_available" in body


def test_invalid_forecast_returns_validation_error():
    response = client.post("/api/forecast", json={"season": 8})
    assert response.status_code == 422


def test_forecast_unavailable_without_model(monkeypatch):
    monkeypatch.setattr("backend.services.prediction_service.load_model", lambda: None)
    body = {"season": 2, "month": 6, "hour": 8, "weekday": 1, "temperature": 0.5, "feels_like": 0.5, "humidity": 0.6, "windspeed": 0.2}
    response = client.post("/api/forecast", json=body)
    assert response.status_code == 503
    assert "No trained model" in response.json()["detail"]


def test_insights_disclose_missing_dataset(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.services.insight_service.DATASET_PATH", tmp_path / "hour.csv")
    response = client.get("/api/insights")
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert "dataset" in response.json()["message"].lower()


def test_today_endpoint_returns_modelled_daily_scenario(monkeypatch):
    expected = {"forecast_date": "2026-10-10", "predictions": [{"hour": 0, "predicted_rentals": 42}] * 24, "peak_hour": 0}
    monkeypatch.setattr("backend.routes.forecast.predict_today", lambda today: expected)
    response = client.get("/api/forecast/today")
    assert response.status_code == 200
    assert response.json() == expected


def test_daily_rentals_calendar_endpoint(tmp_path, monkeypatch):
    import pandas as pd
    frame = pd.DataFrame({"dteday": ["2012-12-01", "2012-12-01"], "hr": [8, 17], "cnt": [12, 25]})
    dataset = tmp_path / "hour.csv"
    frame.to_csv(dataset, index=False)
    monkeypatch.setattr("backend.services.insight_service.DATASET_PATH", dataset)
    response = client.get("/api/insights/calendar?year=2012&month=12")
    assert response.status_code == 200
    assert response.json()["days"][0]["rentals"] == 37
    assert "not advance reservations" in response.json()["metric_name"]


def test_date_range_insights_endpoint_returns_inclusive_summary(tmp_path, monkeypatch):
    import pandas as pd
    frame = pd.DataFrame({"dteday": ["2012-12-01", "2012-12-02"], "hr": [8, 9], "cnt": [10, 20]})
    dataset = tmp_path / "hour.csv"
    frame.to_csv(dataset, index=False)
    monkeypatch.setattr("backend.services.insight_service.DATASET_PATH", dataset)
    response = client.get("/api/insights/range?start_date=2012-12-01&end_date=2012-12-02")
    assert response.status_code == 200
    assert response.json()["total_rentals"] == 30
    assert response.json()["days_with_data"] == 2


def test_ai_status_never_returns_api_key(monkeypatch):
    monkeypatch.setattr("backend.services.ai_insight_service.GROQ_API_KEY", "test-only-secret")
    response = client.get("/api/insights/ai/status")
    assert response.status_code == 200
    assert response.json()["available"] is True
    assert "test-only-secret" not in response.text


def test_final_action_decision_cannot_be_reversed():
    created = client.post("/api/actions", json={"title": "Check roster", "description": "Review coverage", "priority": "HIGH"})
    assert created.status_code == 200
    action_id = created.json()["id"]
    approved = client.patch(f"/api/actions/{action_id}", json={"status": "APPROVED"})
    assert approved.status_code == 200
    reversed_decision = client.patch(f"/api/actions/{action_id}", json={"status": "REJECTED"})
    assert reversed_decision.status_code == 409
