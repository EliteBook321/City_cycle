"""Operations and action-center schemas."""
from typing import Literal
from pydantic import BaseModel, Field

ActionStatus = Literal["PENDING_APPROVAL", "APPROVED", "REJECTED", "EDITED"]


class RecommendRequest(BaseModel):
    forecast_demand: int = Field(ge=0)
    threshold: int = Field(ge=0)
    capacity: int | None = Field(default=None, ge=0)
    budget: float | None = Field(default=None, ge=0)
    priority: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    period: str = Field(default="Selected forecast period", max_length=120)


class ActionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    priority: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    period: str = Field(default="Unspecified", max_length=120)
    estimated_demand: int | None = Field(default=None, ge=0)
    status: ActionStatus = "PENDING_APPROVAL"


class ActionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, min_length=1, max_length=1000)
    priority: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    status: ActionStatus | None = None


class ActionRecord(ActionCreate):
    id: str
    created_at: str
