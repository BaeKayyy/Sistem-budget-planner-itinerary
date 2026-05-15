from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class User(BaseModel):
    id: str
    username: str
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class FavoriteCreate(BaseModel):
    place_name: str = Field(min_length=1)
    place_type: str = Field(min_length=1)
    rating: float | None = Field(default=None, ge=0, le=5)
    price_estimate: int = Field(ge=0)


class Favorite(FavoriteCreate):
    id: str
    user_id: str
    created_at: datetime


class HistoryCreate(BaseModel):
    query: str = Field(min_length=1)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        query = value.strip()
        if not query:
            raise ValueError("Search query cannot be empty.")
        return query


class History(HistoryCreate):
    id: str
    user_id: str
    created_at: datetime


class RecommendationItem(BaseModel):
    name: str
    type: str
    rating: float | None = None
    price_estimate: int
    similarity_score: float


class RecommendationResponse(BaseModel):
    query: str
    filter_type: str | None = None
    total_results: int
    results: list[RecommendationItem]


class SystemStatusResponse(BaseModel):
    dataset_rows: int
    matrix_shape: list[int]
    vocabulary_size: int
    similarity_matrix_shape: list[int] | None = None


class BudgetItem(BaseModel):
    hotel: int = Field(ge=0)
    wisata: int = Field(ge=0)
    kuliner: int = Field(ge=0)
    oleh_oleh: int = Field(default=0, ge=0)
    transport: int = Field(default=0, ge=0)


class AllocationPercent(BaseModel):
    hotel: int = Field(ge=0, le=100)
    wisata: int = Field(ge=0, le=100)
    kuliner: int = Field(ge=0, le=100)
    oleh_oleh: int = Field(ge=0, le=100)
    transport: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_total_percentage(self):
        total = self.hotel + self.wisata + self.kuliner + self.oleh_oleh + self.transport
        if total != 100:
            raise ValueError("Total allocation percentage must be 100%.")
        return self


class BudgetPlannerRequest(BaseModel):
    destination: str = Field(min_length=1)
    days: int = Field(ge=1, le=14)
    budget: int = Field(gt=0)
    people: int = Field(default=1, ge=1)
    interests: list[str] = Field(default_factory=list)
    allocation_mode: Literal["default", "custom"] = "default"
    custom_allocation: AllocationPercent | None = None
    transport_mode: Literal["motor_pribadi", "mobil_pribadi", "ojol"] = "motor_pribadi"

    @model_validator(mode="after")
    def validate_custom_allocation(self):
        if self.allocation_mode == "custom" and self.custom_allocation is None:
            raise ValueError("custom_allocation is required when allocation_mode is custom.")
        return self


class BudgetPlannerResponse(BaseModel):
    destination: str
    budget_total: int
    days: int
    people: int
    budget_per_day: int
    budget_per_person: int
    allocation_mode: str
    allocation_percent: AllocationPercent
    allocation: BudgetItem
    transport_mode: str
    transport_estimate: int
    transport_within_budget: bool
    user_budget: int
    estimated_total_cost: int
    remaining_budget: int
    over_budget: bool
    breakdown: BudgetItem
    recommendations: list[str]


class ItineraryGenerateRequest(BaseModel):
    destination: str = Field(min_length=1)
    days: int = Field(ge=1, le=14)
    budget: int = Field(gt=0)
    people: int = Field(default=1, ge=1)
    interests: list[str] = Field(default_factory=list)
    allocation_mode: Literal["default", "custom"] = "default"
    custom_allocation: AllocationPercent | None = None
    transport_mode: Literal["motor_pribadi", "mobil_pribadi", "ojol"] = "motor_pribadi"

    @model_validator(mode="after")
    def validate_custom_allocation(self):
        if self.allocation_mode == "custom" and self.custom_allocation is None:
            raise ValueError("custom_allocation is required when allocation_mode is custom.")
        return self


class ItineraryPlace(BaseModel):
    name: str
    type: str
    price_estimate: int = Field(ge=0)
    rating: float | None = None


class ItineraryDay(BaseModel):
    day: int = Field(ge=1)
    places: list[ItineraryPlace]
    day_cost: int = Field(ge=0)


class Itinerary(BaseModel):
    id: str
    user_id: str
    destination: str
    people: int = 1
    days: list[ItineraryDay]
    estimated_total_cost: int = Field(ge=0)
    budget: int = Field(ge=0)
    allocation: BudgetItem | None = None
    allocation_percent: AllocationPercent | None = None
    transport_mode: str | None = None
    transport_estimate: int = 0
    within_budget: bool
    created_at: datetime


# Backward-friendly names used by the existing API code and documentation.
UserLogin = LoginRequest
UserResponse = User
FavoriteResponse = Favorite
SearchHistoryCreate = HistoryCreate
SearchHistoryResponse = History
Budget = BudgetPlannerResponse
ItineraryResponse = Itinerary
