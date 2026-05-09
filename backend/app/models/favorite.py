from datetime import datetime

from pydantic import BaseModel, Field


class FavoriteBase(BaseModel):
    place_name: str = Field(
        min_length=1,
        description="Name of the saved place.",
        examples=["Pantai Jogan"],
    )
    place_type: str = Field(
        min_length=1,
        description="Type of place, for example wisata, kuliner, or hotel.",
        examples=["wisata"],
    )
    rating: float | None = Field(
        default=None,
        ge=0,
        le=5,
        description="Place rating from 0 to 5 when available.",
        examples=[4.3],
    )
    price_estimate: int = Field(
        ge=0,
        description="Estimated price for the place. Must not be negative.",
        examples=[10000],
    )


class FavoriteCreate(FavoriteBase):
    # user_id is intentionally not accepted from the frontend.
    # It must come from the authenticated JWT user later to prevent users
    # from creating favorites for another account.
    pass


class FavoriteResponse(FavoriteBase):
    id: str = Field(
        description="Public favorite identifier returned by the API.",
        examples=["665f1c2d8b4f5f0012a34567"],
    )
    user_id: str = Field(
        description="Authenticated user identifier that owns this favorite.",
        examples=["665f1c2d8b4f5f0012a11111"],
    )
    created_at: datetime = Field(
        description="UTC timestamp when this favorite was created.",
        examples=["2026-05-10T10:30:00Z"],
    )
