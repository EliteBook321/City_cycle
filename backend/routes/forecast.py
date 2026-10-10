"""Forecast endpoints."""
from fastapi import APIRouter, HTTPException
from datetime import date
from backend.schemas.forecast_schema import ForecastInput, CompareRequest
from backend.services.prediction_service import predict, predict_today

router = APIRouter(prefix="/api/forecast", tags=["forecast"])

@router.post("")
def forecast(payload: ForecastInput):
    try:
        return predict(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@router.get("/today")
def forecast_today_endpoint():
    try:
        return predict_today(date.today())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@router.post("/compare")
def compare(payload: CompareRequest):
    try:
        return {"scenario_a": predict(payload.scenario_a), "scenario_b": predict(payload.scenario_b)}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
