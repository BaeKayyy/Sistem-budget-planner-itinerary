from fastapi import APIRouter, HTTPException, Query, status

from app.services.recommender import (
    RecommenderLoadError,
    get_system_status,
    recommend_places,
)


router = APIRouter(tags=["Recommendations"])


@router.get("/recommend")
def get_recommendations(
    q: str = Query(
        ...,
        min_length=1,
        description="Search query, for example: pantai, cafe, or hotel murah.",
    ),
    filter_type: str | None = Query(
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
) -> dict:
    query = q.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'q' cannot be empty.",
        )

    normalized_filter_type = filter_type.strip().lower() if filter_type else None

    try:
        results = recommend_places(
            query=query,
            filter_type=normalized_filter_type,
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

    return {
        "query": query,
        "filter_type": normalized_filter_type,
        "total_results": len(results),
        "results": results,
    }


@router.get("/system/status")
def get_status() -> dict:
    try:
        return get_system_status()
    except RecommenderLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
