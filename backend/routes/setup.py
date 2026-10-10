"""One-click setup: install authentic source data and train a matching model."""
from fastapi import APIRouter, HTTPException
from backend.services.dataset_service import initialize_project

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.post("/initialize")
def initialize(force_retrain: bool = False):
    try:
        return initialize_project(force_retrain=force_retrain)
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=f"CityCycle setup could not complete: {exc}") from exc
