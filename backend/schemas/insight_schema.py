"""Request contracts for date-range demand analysis."""
from datetime import date
from pydantic import BaseModel, Field, model_validator


class DateRangeRequest(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.end_date - self.start_date).days > 730:
            raise ValueError("date range must not exceed 731 days")
        return self
