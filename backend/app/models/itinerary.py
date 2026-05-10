from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class ItineraryGenerateRequest(BaseModel):
    """Payload required to generate a personalised itinerary."""

    destination: str = Field(
        min_length=1,
        description="City or region name for the trip, for example Yogyakarta.",
        examples=["Yogyakarta"],
    )
    days: int = Field(
        ge=1,
        le=14,
        description="Total number of travel days (1 – 14).",
        examples=[2],
    )
    budget: int = Field(
        ge=0,
        description="Total trip budget in IDR. Used to filter or flag over-budget plans.",
        examples=[500000],
    )
    interests: list[str] = Field(
        default_factory=list,
        description=(
            "List of interest keywords used to personalise place selection, "
            "for example pantai, kuliner, or cafe."
        ),
        examples=[["pantai", "kuliner", "cafe"]],
    )


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ItineraryPlace(BaseModel):
    """A single place scheduled inside a day of the itinerary."""

    name: str = Field(
        description="Display name of the place.",
        examples=["Pantai Parangtritis"],
    )
    type: str = Field(
        description="Place category: wisata, kuliner, hotel, or cafe.",
        examples=["wisata"],
    )
    price_estimate: int = Field(
        ge=0,
        description="Estimated cost for this place in IDR.",
        examples=[25000],
    )
    rating: float | None = Field(
        default=None,
        description="Average rating from 0 to 5 when available.",
        examples=[4.5],
    )


class ItineraryDay(BaseModel):
    """All places planned for a single day."""

    day: int = Field(
        ge=1,
        description="Day number, starting from 1.",
        examples=[1],
    )
    places: list[ItineraryPlace] = Field(
        description="Ordered list of places to visit on this day.",
    )
    day_cost: int = Field(
        ge=0,
        description="Sum of all place price estimates for this day in IDR.",
        examples=[75000],
    )


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class ItineraryResponse(BaseModel):
    """Full itinerary returned after generation or retrieved from storage."""

    id: str = Field(
        description="MongoDB ObjectId of the saved itinerary.",
        examples=["665f1c2d8b4f5f0012a34567"],
    )
    user_id: str = Field(
        description="Authenticated user that owns this itinerary.",
        examples=["665f1c2d8b4f5f0012a11111"],
    )
    destination: str = Field(
        description="Trip destination.",
        examples=["Yogyakarta"],
    )
    days: list[ItineraryDay] = Field(
        description="Day-by-day breakdown of the trip.",
    )
    estimated_total_cost: int = Field(
        ge=0,
        description="Accumulated cost across all days in IDR.",
        examples=[300000],
    )
    budget: int = Field(
        ge=0,
        description="Original requested budget in IDR.",
        examples=[500000],
    )
    within_budget: bool = Field(
        description="True when estimated_total_cost does not exceed budget.",
        examples=[True],
    )
    created_at: datetime = Field(
        description="UTC timestamp when the itinerary was created.",
        examples=["2026-05-10T10:30:00Z"],
    )
