from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BaselineOut(BaseModel):
    """One stored baseline row (per metric, per rolling window)."""

    metric_type: str
    period_days: int
    n: int
    mean: float
    std: float
    min: float = Field(validation_alias="min_val", serialization_alias="min")
    max: float = Field(validation_alias="max_val", serialization_alias="max")
    computed_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class BaselineListOut(BaseModel):
    baselines: list[BaselineOut]
