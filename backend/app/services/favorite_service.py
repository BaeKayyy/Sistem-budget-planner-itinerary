from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from ..database.mongodb import MongoDBConnectionError, get_database
from ..models.favorite import FavoriteCreate


FAVORITES_COLLECTION = "favorites"


class FavoriteServiceError(RuntimeError):
    """Raised when a favorite database operation fails."""


class FavoriteNotFoundError(FavoriteServiceError):
    """Raised when a favorite does not exist for the current user."""


def _favorites_collection():
    try:
        return get_database()[FAVORITES_COLLECTION]
    except MongoDBConnectionError as exc:
        raise FavoriteServiceError(str(exc)) from exc


def serialize_mongo_document(document: dict) -> dict:
    return {
        "id": str(document["_id"]),
        "user_id": document["user_id"],
        "place_name": document["place_name"],
        "place_type": document["place_type"],
        "rating": document.get("rating"),
        "price_estimate": document["price_estimate"],
        "created_at": document["created_at"],
    }


def create_favorite(user_id: str, favorite_data: FavoriteCreate) -> dict:
    favorite_document = {
        # user_id must come from the authenticated JWT user, never the frontend.
        "user_id": user_id,
        "place_name": favorite_data.place_name,
        "place_type": favorite_data.place_type,
        "rating": favorite_data.rating,
        "price_estimate": favorite_data.price_estimate,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = _favorites_collection().insert_one(favorite_document)
    except PyMongoError as exc:
        raise FavoriteServiceError(f"Failed to create favorite: {exc}") from exc

    favorite_document["_id"] = result.inserted_id
    return serialize_mongo_document(favorite_document)


def get_favorites_by_user(user_id: str) -> list[dict]:
    try:
        favorites = _favorites_collection().find({"user_id": user_id}).sort(
            "created_at",
            DESCENDING,
        )
    except PyMongoError as exc:
        raise FavoriteServiceError(f"Failed to fetch favorites: {exc}") from exc

    return [serialize_mongo_document(favorite) for favorite in favorites]


def delete_favorite(user_id: str, favorite_id: str) -> None:
    try:
        object_id = ObjectId(favorite_id)
    except InvalidId as exc:
        raise FavoriteNotFoundError("Favorite was not found.") from exc

    try:
        result = _favorites_collection().delete_one(
            {
                "_id": object_id,
                "user_id": user_id,
            }
        )
    except PyMongoError as exc:
        raise FavoriteServiceError(f"Failed to delete favorite: {exc}") from exc

    if result.deleted_count == 0:
        raise FavoriteNotFoundError("Favorite was not found.")
