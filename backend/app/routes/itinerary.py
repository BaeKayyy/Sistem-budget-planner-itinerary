from fastapi import APIRouter, Depends, HTTPException, Path, status

from ..models.itinerary import ItineraryGenerateRequest, ItineraryResponse
from ..models.user import UserResponse
from ..services.itinerary_service import (
    ItineraryNotFoundError,
    ItineraryServiceError,
    delete_itinerary,
    generate_itinerary,
    get_itineraries_by_user,
)
from .auth import get_current_user


router = APIRouter(
    prefix="/itinerary",
    tags=["Itinerary"],
)

# ---------------------------------------------------------------------------
# Generate & save
# ---------------------------------------------------------------------------


@router.post(
    "/generate",
    response_model=ItineraryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and save a personalised itinerary",
    description=(
        "Automatically build a day-by-day travel plan based on the user's "
        "destination, trip length, budget, and interests. "
        "Places are sourced from the recommendation dataset using TF-IDF "
        "similarity. The generated itinerary is persisted to MongoDB and "
        "returned immediately.\n\n"
        "**Rules applied during generation:**\n"
        "- Each day follows a *wisata → kuliner/cafe → hotel* template\n"
        "- Kuliner and cafe slots alternate across days for variety\n"
        "- Duplicate places are avoided across the whole itinerary\n"
        "- The engine tries to keep the estimated cost within budget\n"
        "- Hotels rotate so the same property is not repeated every night"
    ),
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
                        "destination": "Yogyakarta",
                        "days": 2,
                        "budget": 500000,
                        "interests": ["pantai", "kuliner", "cafe"],
                    }
                }
            }
        }
    },
)
def generate_itinerary_endpoint(
    request: ItineraryGenerateRequest,
    current_user: UserResponse = Depends(get_current_user),
) -> ItineraryResponse:
    try:
        itinerary = generate_itinerary(
            user_id=current_user.id,
            request=request,
        )
    except ItineraryServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return ItineraryResponse(**itinerary)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[ItineraryResponse],
    summary="Get all itineraries for the authenticated user",
    description=(
        "Return every saved itinerary that belongs to the currently "
        "authenticated user, sorted with the newest itinerary first. "
        "Other users' itineraries are never exposed."
    ),
)
def list_itineraries(
    current_user: UserResponse = Depends(get_current_user),
) -> list[ItineraryResponse]:
    try:
        itineraries = get_itineraries_by_user(current_user.id)
    except ItineraryServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return [ItineraryResponse(**itinerary) for itinerary in itineraries]


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete(
    "/{itinerary_id}",
    response_model=dict[str, str],
    summary="Delete an itinerary",
    description=(
        "Permanently remove an itinerary identified by its MongoDB ObjectId. "
        "The operation is scoped to the authenticated user — a user cannot "
        "delete another user's itinerary."
    ),
)
def delete_itinerary_endpoint(
    itinerary_id: str = Path(
        ...,
        description="MongoDB ObjectId of the itinerary to delete.",
        examples=["665f1c2d8b4f5f0012a34567"],
    ),
    current_user: UserResponse = Depends(get_current_user),
) -> dict[str, str]:
    try:
        delete_itinerary(
            user_id=current_user.id,
            itinerary_id=itinerary_id,
        )
    except ItineraryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ItineraryServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {"message": "Itinerary deleted successfully."}
