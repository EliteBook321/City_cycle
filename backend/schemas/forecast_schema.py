"""Validated forecast request and response models."""
from pydantic import BaseModel, Field


class ForecastInput(BaseModel):
    year: int = Field(default=1, ge=0, le=1, description="Dataset year indicator: 0=2011, 1=2012")
    season: int = Field(ge=1, le=4)
    month: int = Field(ge=1, le=12)
    hour: int = Field(ge=0, le=23)
    holiday: int = Field(default=0, ge=0, le=1)
    weekday: int = Field(ge=0, le=6)
    workingday: int = Field(default=1, ge=0, le=1)
    weather: int = Field(default=1, ge=1, le=4, description="Bike Sharing dataset weather category")
    temperature: float = Field(ge=0, le=1)
    feels_like: float = Field(ge=0, le=1)
    humidity: float = Field(ge=0, le=1)
    windspeed: float = Field(ge=0, le=1)


class ForecastResponse(BaseModel):
    predicted_rentals: int = Field(ge=0)
    model_name: str
    model_version: str
    estimate_note: str


class CompareRequest(BaseModel):
    scenario_a: ForecastInput
    scenario_b: ForecastInput
