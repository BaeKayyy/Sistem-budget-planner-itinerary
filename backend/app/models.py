from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


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
    wisata: int = Field(ge=0)
    kuliner: int = Field(ge=0)
    oleh_oleh: int = Field(default=0, ge=0)
    hotel: int = Field(ge=0)
    transport: int = Field(default=0, ge=0)


class BudgetPlannerRequest(BaseModel):
    destination: str = Field(min_length=1)
    days: int = Field(ge=1, le=14)
    budget: int = Field(ge=0)
    interests: list[str] = Field(default_factory=list)


class BudgetPlannerResponse(BaseModel):
    destination: str
    days: int
    user_budget: int
    estimated_total_cost: int
    remaining_budget: int
    over_budget: bool
    breakdown: BudgetItem
    recommendations: list[str]


class ItineraryGenerateRequest(BaseModel):
    destination: str = Field(min_length=1)
    days: int = Field(ge=1, le=14)
    budget: int = Field(ge=0)
    interests: list[str] = Field(default_factory=list)


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
    days: list[ItineraryDay]
    estimated_total_cost: int = Field(ge=0)
    budget: int = Field(ge=0)
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
