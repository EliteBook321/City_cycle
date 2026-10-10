from backend.schemas.action_schema import RecommendRequest, ActionPatch
from backend.services.optimizer_service import recommend
from backend.services.action_service import create_action, update_action
from backend.schemas.action_schema import ActionCreate
import pytest


def test_below_threshold_has_no_recommendations():
    assert recommend(RecommendRequest(forecast_demand=400, threshold=500)) == []


def test_recommendation_includes_capacity_gap_and_urgency():
    result = recommend(RecommendRequest(forecast_demand=900, threshold=500, capacity=650, priority="LOW"))
    assert result[0]["capacity_gap"] == 250
    assert result[0]["priority"] == "HIGH"
    assert result[0]["advisory_only"] is True


def test_zero_budget_avoids_cost_incurring_action():
    result = recommend(RecommendRequest(forecast_demand=700, threshold=500, budget=0))
    assert "zero" in result[0]["explanation"]


def test_action_status_transitions():
    action = create_action(ActionCreate(title="Check", description="Review", priority="MEDIUM"))
    edited = update_action(action["id"], ActionPatch(description="Clarified plan", status="EDITED"))
    assert edited["status"] == "EDITED"
    updated = update_action(action["id"], ActionPatch(status="APPROVED"))
    assert updated["status"] == "APPROVED"
    with pytest.raises(ValueError, match="is final"):
        update_action(action["id"], ActionPatch(status="REJECTED"))
    assert update_action("missing", ActionPatch(status="REJECTED")) is None
