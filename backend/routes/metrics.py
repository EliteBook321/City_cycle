"""Model metrics endpoint."""
from fastapi import APIRouter
from backend.services.evaluation_service import get_metrics
router = APIRouter(prefix="/api/metrics", tags=["metrics"])

@router.get("")
def metrics():
    return get_metrics()
