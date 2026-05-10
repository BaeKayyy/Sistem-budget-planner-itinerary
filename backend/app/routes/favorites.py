from fastapi import APIRouter, Depends, HTTPException, Path, status

from ..models.favorite import FavoriteCreate, FavoriteResponse
from ..models.user import UserResponse
from ..services.favorite_service import (
    FavoriteNotFoundError,
    FavoriteServiceError,
    create_favorite,
    delete_favorite,
    get_favorites_by_user,
)
from .auth import get_current_user


router = APIRouter(prefix="/favorites", tags=["Favorites"])


@router.post(
    "",
    response_model=FavoriteResponse,
    status_code=status.HTTP_201_CREATED,
    description="Save a place to the current authenticated user's favorites.",
)
def add_favorite(
    favorite_data: FavoriteCreate,
    current_user: UserResponse = Depends(get_current_user),
) -> FavoriteResponse:
    try:
        favorite = create_favorite(
            user_id=current_user.id,
            favorite_data=favorite_data,
        )
    except FavoriteServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return FavoriteResponse(**favorite)


@router.get(
    "",
    response_model=list[FavoriteResponse],
    description="Return favorites belonging to the current authenticated user.",
)
def read_favorites(
    current_user: UserResponse = Depends(get_current_user),
) -> list[FavoriteResponse]:
    try:
        favorites = get_favorites_by_user(current_user.id)
    except FavoriteServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return [FavoriteResponse(**favorite) for favorite in favorites]


@router.delete(
    "/{favorite_id}",
    response_model=dict[str, str],
    description="Delete one favorite owned by the current authenticated user.",
)
def remove_favorite(
    favorite_id: str = Path(
        ...,
        description="MongoDB ObjectId of the favorite to delete.",
        examples=["665f1c2d8b4f5f0012a34567"],
    ),
    current_user: UserResponse = Depends(get_current_user),
) -> dict[str, str]:
    try:
        delete_favorite(
            user_id=current_user.id,
            favorite_id=favorite_id,
        )
    except FavoriteNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except FavoriteServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {"message": "Favorite deleted successfully."}
