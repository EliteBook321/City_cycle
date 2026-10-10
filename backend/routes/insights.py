"""Historical insights endpoint."""
from datetime import date
from fastapi import APIRouter, HTTPException, Query
from backend.schemas.insight_schema import DateRangeRequest
from backend.services.ai_insight_service import explain_date_range, get_ai_status
from backend.services.insight_service import get_date_range_summary, get_insights, get_month_calendar
router = APIRouter(prefix="/api/insights", tags=["insights"])

@router.get("")
def insights():
    return get_insights()


@router.get("/calendar")
def calendar_month(year: int = Query(2012, ge=2011, le=2035), month: int = Query(12, ge=1, le=12)):
    return get_month_calendar(year, month)


@router.get("/range")
def insights_range(start_date: date, end_date: date):
    try:
        request = DateRangeRequest(start_date=start_date, end_date=end_date)
        return get_date_range_summary(request.start_date, request.end_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/ai/status")
def ai_status():
    return get_ai_status()


@router.post("/ai-summary")
def ai_summary(request: DateRangeRequest):
    summary = get_date_range_summary(request.start_date, request.end_date)
    try:
        return explain_date_range(summary)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
