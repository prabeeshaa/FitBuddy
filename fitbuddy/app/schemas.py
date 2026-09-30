from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


GOAL_OPTIONS = ("weight loss", "muscle gain", "general wellness", "flexibility", "endurance")
INTENSITY_OPTIONS = ("low", "medium", "high")


class UserInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=80)
    user_id: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    age: int = Field(ge=13, le=100)
    weight_kg: float = Field(gt=25, le=400)
    goal: str = Field(min_length=3, max_length=40)
    intensity: Literal["low", "medium", "high"]

    @field_validator("goal")
    @classmethod
    def normalize_goal(cls, value: str) -> str:
        value = " ".join(value.lower().split())
        if value not in GOAL_OPTIONS:
            raise ValueError(f"goal must be one of: {', '.join(GOAL_OPTIONS)}")
        return value


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    feedback: str = Field(min_length=3, max_length=1000)


class NutritionTipRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=40)

    @field_validator("goal")
    @classmethod
    def normalize_goal(cls, value: str) -> str:
        value = " ".join(value.lower().split())
        if value not in GOAL_OPTIONS:
            raise ValueError(f"goal must be one of: {', '.join(GOAL_OPTIONS)}")
        return value


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    name: str
    age: int
    weight_kg: float
    goal: str
    intensity: str


class PlanResponse(BaseModel):
    user: UserSummary
    original_plan: str
    updated_plan: str | None = None
    nutrition_tip: str
    latest_feedback: str | None = None
    feedback_count: int
    ai_source: str


class GenerateResponse(PlanResponse):
    message: str = "Your personalized plan is ready."

