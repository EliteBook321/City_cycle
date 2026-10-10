"""Transparent capacity-aware advisory rules."""
from backend.schemas.action_schema import RecommendRequest


def recommend(request: RecommendRequest) -> list[dict]:
    if request.forecast_demand <= request.threshold:
        return []
    gap = max(0, request.forecast_demand - request.capacity) if request.capacity is not None else None
    urgency = request.priority
    if request.forecast_demand >= request.threshold * 1.5:
        urgency = "HIGH"
    exceedance = request.forecast_demand - request.threshold
    if gap is None:
        capacity_reason = "No comparable hourly capacity was supplied, so a staffing or fleet shortfall cannot be quantified."
    elif gap > 0:
        capacity_reason = f"The supplied hourly capacity is short by {gap:,} rentals; this is a citywide rental-equivalent gap, not a bike count."
    else:
        capacity_reason = "The supplied hourly capacity covers this scenario, but does not describe station-level dock or bike availability."
    if request.budget == 0:
        budget_note = " Budget is zero: limit this to coordination and readiness checks; do not assume paid additions."
    elif request.budget is not None:
        budget_note = f" Respect the configured budget cap of {request.budget:,.2f}; no intervention cost is estimated by this prototype."
    else:
        budget_note = " No budget was supplied, so cost feasibility is unknown."
    common = {"period": request.period, "estimated_demand": request.forecast_demand, "capacity_gap": gap, "advisory_only": True}
    return [
        {"title": "Check staffing readiness before the forecast window", "explanation": f"Forecast is {exceedance:,} rentals above the configured threshold of {request.threshold:,}. Review roster coverage before {request.period}.{budget_note}", "priority": urgency, **common},
        {"title": "Review citywide bike rebalancing capacity", "explanation": f"{capacity_reason} Consider reviewing the system-level plan before {request.period}; no station route, exact bike quantity, or automatic dispatch can be derived here.{budget_note}", "priority": urgency if gap is None or gap > 0 else request.priority, **common},
    ]
