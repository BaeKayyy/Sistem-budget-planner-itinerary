from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.models.recommendation import RecommendationResponse, SystemStatusResponse
from app.services.recommender import (
    RecommenderLoadError,
    get_system_status,
    recommend_places,
)


router = APIRouter(tags=["Recommendations"])
PlaceType = Literal["wisata", "kuliner", "hotel"]


@router.get("/recommend", response_model=RecommendationResponse)
def get_recommendations(
    q: str = Query(
        ...,
        min_length=1,
        description="Search query, for example: pantai, cafe, or hotel murah.",
    ),
    filter_type: PlaceType | None = Query(
        default=None,
        alias="type",
        description="Optional place type filter. Use: wisata, kuliner, or hotel.",
    ),
    top_k: int = Query(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of recommendations to return.",
    ),
) -> RecommendationResponse:
    query = q.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'q' cannot be empty.",
        )

    try:
        results = recommend_places(
            query=query,
            filter_type=filter_type,
            top_k=top_k,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RecommenderLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendations found for the given query.",
        )

    return RecommendationResponse(
        query=query,
        filter_type=filter_type,
        total_results=len(results),
        results=results,
    )


@router.get("/system/status", response_model=SystemStatusResponse)
def get_status() -> SystemStatusResponse:
    try:
        status_data = get_system_status()
    except RecommenderLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return SystemStatusResponse(
        dataset_rows=status_data["dataset_rows"],
        matrix_shape=list(status_data["tfidf_matrix_shape"]),
        vocabulary_size=status_data["vectorizer_vocabulary_size"],
    )
