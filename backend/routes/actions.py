"""Action center and operations endpoints."""
import csv
import io
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from backend.schemas.action_schema import RecommendRequest, ActionCreate, ActionPatch
from backend.services.optimizer_service import recommend
from backend.services.action_service import list_actions, create_action, update_action

router = APIRouter(prefix="/api/actions", tags=["actions"])

@router.post("/recommend")
def make_recommendations(payload: RecommendRequest):
    return {"recommendations": recommend(payload)}

@router.get("")
def get_actions():
    return {"actions": list_actions(), "persistence": "in-memory; actions reset when backend restarts"}

@router.post("")
def add_action(payload: ActionCreate):
    return create_action(payload)

@router.patch("/{action_id}")
def patch_action(action_id: str, payload: ActionPatch):
    try:
        result = update_action(action_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Action not found")
    return result

@router.get("/export")
def export_actions():
    buffer = io.StringIO()
    rows = list_actions()
    fields = ["id", "title", "description", "priority", "period", "estimated_demand", "status", "created_at"]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=citycycle-actions.csv"})
