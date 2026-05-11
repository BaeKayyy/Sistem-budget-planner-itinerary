from pydantic import BaseModel, Field


class BudgetItem(BaseModel):
    """Breakdown of costs per category."""

    wisata: int = Field(ge=0, description="Estimated cost for sightseeing and attractions in IDR.", examples=[50000])
    kuliner: int = Field(ge=0, description="Estimated cost for food and beverages in IDR.", examples=[120000])
    hotel: int = Field(ge=0, description="Estimated cost for accommodation in IDR.", examples=[300000])


class BudgetPlannerRequest(BaseModel):
    """Payload required to plan a budget for a trip."""

    destination: str = Field(
        min_length=1,
        description="City or region name for the trip.",
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
        description="Total trip budget in IDR.",
        examples=[500000],
    )
    interests: list[str] = Field(
        default_factory=list,
        description="List of interest keywords to personalize cost estimates.",
        examples=[["pantai", "kuliner", "hotel"]],
    )


class BudgetPlannerResponse(BaseModel):
    """Result of the budget planning process."""

    destination: str = Field(description="Trip destination.", examples=["Yogyakarta"])
    days: int = Field(description="Total trip duration in days.", examples=[2])
    user_budget: int = Field(description="Original budget provided by the user in IDR.", examples=[500000])
    estimated_total_cost: int = Field(description="Calculated total trip cost in IDR.", examples=[470000])
    remaining_budget: int = Field(description="Difference between user budget and estimated cost.", examples=[30000])
    over_budget: bool = Field(description="Flag indicating if the trip exceeds the user's budget.", examples=[False])
    breakdown: BudgetItem = Field(description="Cost breakdown by category.")
    recommendations: list[str] = Field(
        description="Smart validation messages and budget advice.",
        examples=[["Budget is sufficient for this trip."]],
    )
