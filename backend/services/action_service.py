"""In-memory action store for the single-user hackathon prototype."""
from datetime import datetime, timezone
from uuid import uuid4
from backend.schemas.action_schema import ActionCreate, ActionPatch

_ACTIONS: dict[str, dict] = {}


def list_actions() -> list[dict]:
    return sorted(_ACTIONS.values(), key=lambda row: row["created_at"], reverse=True)


def create_action(payload: ActionCreate) -> dict:
    record = payload.model_dump() | {"id": str(uuid4()), "created_at": datetime.now(timezone.utc).isoformat()}
    _ACTIONS[record["id"]] = record
    return record


def update_action(action_id: str, patch: ActionPatch) -> dict | None:
    row = _ACTIONS.get(action_id)
    if row is None:
        return None
    changes = patch.model_dump(exclude_unset=True, exclude_none=True)
    current_status = row["status"]
    requested_status = changes.get("status", current_status)
    final_statuses = {"APPROVED", "REJECTED"}
    if current_status in final_statuses and changes != {"status": current_status}:
        raise ValueError(f"{current_status} is final; create a new action instead of changing a decided record.")
    allowed_transitions = {
        "PENDING_APPROVAL": {"PENDING_APPROVAL", "APPROVED", "REJECTED", "EDITED"},
        "EDITED": {"EDITED", "APPROVED", "REJECTED"},
        "APPROVED": {"APPROVED"},
        "REJECTED": {"REJECTED"},
    }
    if requested_status not in allowed_transitions[current_status]:
        raise ValueError(f"Cannot transition action from {current_status} to {requested_status}.")
    if current_status in final_statuses and requested_status == current_status:
        return row
    row.update(changes)
    return row
