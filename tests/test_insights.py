from datetime import date
import pandas as pd
from backend.services import insight_service


def test_insights_compute_workday_regimes_year_weather_and_ops_guidance(tmp_path, monkeypatch):
    rows = []
    for date, is_workday, year_flag in (("2011-01-03", 1, 0), ("2012-01-03", 1, 1), ("2012-01-07", 0, 1)):
        for hour in range(24):
            demand = 20 + (180 if hour in (8, 17) and is_workday else 90 if 12 <= hour <= 15 and not is_workday else 0)
            rows.append({"dteday": date, "hr": hour, "cnt": demand, "weekday": 1 if is_workday else 6, "workingday": is_workday, "weathersit": 1 if hour % 2 else 3, "season": 1, "yr": year_flag, "temp": hour / 24})
    dataset_path = tmp_path / "hour.csv"
    pd.DataFrame(rows).to_csv(dataset_path, index=False)
    monkeypatch.setattr(insight_service, "DATASET_PATH", dataset_path)
    monkeypatch.setattr(insight_service, "load_model", lambda: None)

    result = insight_service.get_insights()

    assert result["available"] is True
    assert result["summaries"]["workday_morning_peak"]["hour"] == 8
    assert result["summaries"]["workday_evening_peak"]["hour"] == 17
    assert set(result["summaries"]["yearly_average"]) == {"2011", "2012"}
    assert result["ops_guidance"]
    assert result["hourly_by_regime"][8]["workingday"] > result["hourly_by_regime"][8]["weekend_or_nonworking"]


def test_month_calendar_aggregates_daily_rentals_not_booking_events(tmp_path, monkeypatch):
    dataset = pd.DataFrame({
        "dteday": ["2012-12-01", "2012-12-01", "2012-12-02"],
        "hr": [8, 17, 9],
        "cnt": [12, 25, 7],
    })
    path = tmp_path / "hour.csv"
    dataset.to_csv(path, index=False)
    monkeypatch.setattr(insight_service, "DATASET_PATH", path)

    result = insight_service.get_month_calendar(2012, 12)

    assert result["available"] is True
    assert result["total_rentals"] == 44
    assert result["days"][0] == {"day": 1, "rentals": 37, "hours_recorded": 2, "peak_hour": 17, "peak_hour_rentals": 25}
    assert "not advance reservations" in result["metric_name"]


def test_month_calendar_discloses_out_of_source_period():
    result = insight_service.get_month_calendar(2026, 10)
    assert result["available"] is False
    assert "2011 to 2012" in result["message"]


def test_date_range_summary_includes_all_days_and_computes_peak(tmp_path, monkeypatch):
    frame = pd.DataFrame({
        "dteday": ["2012-12-01", "2012-12-01", "2012-12-02", "2012-12-03"],
        "hr": [8, 17, 9, 10],
        "cnt": [12, 25, 7, 31],
        "workingday": [0, 0, 0, 1],
        "weathersit": [1, 1, 2, 1],
        "temp": [0.4, 0.5, 0.3, 0.6],
        "season": [4, 4, 4, 4],
    })
    dataset = tmp_path / "hour.csv"
    frame.to_csv(dataset, index=False)
    monkeypatch.setattr(insight_service, "DATASET_PATH", dataset)

    result = insight_service.get_date_range_summary(date(2012, 12, 1), date(2012, 12, 2))

    assert result["available"] is True
    assert result["days_with_data"] == 2
    assert result["total_rentals"] == 44
    assert result["peak_day"]["date"] == "2012-12-01"
    assert result["peak_day"]["rentals"] == 37
    assert len(result["largest_observed_category_spreads"]) <= 3


def test_date_range_summary_rejects_reversed_dates():
    import pytest
    with pytest.raises(ValueError, match="on or after"):
        insight_service.get_date_range_summary(date(2012, 12, 2), date(2012, 12, 1))


def test_groq_explanation_uses_aggregates_and_never_returns_key(monkeypatch):
    from backend.services import ai_insight_service

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "Peak day is notable. Review staffing. Historical aggregates are not live bookings."}}]}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, headers, json):
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(ai_insight_service, "GROQ_API_KEY", "test-secret-value")
    monkeypatch.setattr(ai_insight_service.httpx, "Client", FakeClient)
    summary = {
        "available": True, "start_date": "2012-12-01", "end_date": "2012-12-02",
        "source_period": {"start": "2012-12-01", "end": "2012-12-02"},
        "days_with_data": 2, "hourly_rows": 48, "total_rentals": 100,
        "average_daily_rentals": 50, "peak_day": {"date": "2012-12-01", "rentals": 60},
        "workingday_daily_averages": {}, "largest_observed_category_spreads": [],
    }

    result = ai_insight_service.explain_date_range(summary)

    assert result["available"] is True
    assert "Peak day is notable" in result["explanation"]
    assert captured["headers"]["Authorization"] == "Bearer test-secret-value"
    assert "test-secret-value" not in str(result)
    assert "individual" not in captured["json"]["messages"][-1]["content"]
