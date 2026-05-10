from fastapi import APIRouter, Depends, HTTPException, status

from ..models.history import SearchHistoryCreate, SearchHistoryResponse
from ..models.user import UserResponse
from ..services.history_service import (
    HistoryServiceError,
    clear_search_history_by_user,
    get_search_history_by_user,
    save_search_history,
)
from .auth import get_current_user


router = APIRouter(prefix="/history", tags=["Search History"])


@router.post(
    "",
    response_model=SearchHistoryResponse,
    status_code=status.HTTP_201_CREATED,
    description="Save a search query for the current authenticated user.",
)
def create_search_history(
    history_data: SearchHistoryCreate,
    current_user: UserResponse = Depends(get_current_user),
) -> SearchHistoryResponse:
    try:
        history_item = save_search_history(
            user_id=current_user.id,
            history_data=history_data,
        )
    except HistoryServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return SearchHistoryResponse(**history_item)


@router.get(
    "",
    response_model=list[SearchHistoryResponse],
    description="Return the latest 20 search history items for the current user.",
)
def read_search_history(
    current_user: UserResponse = Depends(get_current_user),
) -> list[SearchHistoryResponse]:
    try:
        history_items = get_search_history_by_user(current_user.id)
    except HistoryServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return [SearchHistoryResponse(**item) for item in history_items]


@router.delete(
    "",
    response_model=dict[str, str | int],
    description="Clear all search history items owned by the current user.",
)
def clear_search_history(
    current_user: UserResponse = Depends(get_current_user),
) -> dict[str, str | int]:
    try:
        deleted_count = clear_search_history_by_user(current_user.id)
    except HistoryServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {
        "message": "Search history cleared successfully.",
        "deleted_count": deleted_count,
    }
