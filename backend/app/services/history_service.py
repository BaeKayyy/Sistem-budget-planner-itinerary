from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from ..database.mongodb import MongoDBConnectionError, get_database
from ..models.history import SearchHistoryCreate


SEARCH_HISTORY_COLLECTION = "search_history"
SEARCH_HISTORY_LIMIT = 20


class HistoryServiceError(RuntimeError):
    """Raised when a search history database operation fails."""


def _history_collection():
    try:
        return get_database()[SEARCH_HISTORY_COLLECTION]
    except MongoDBConnectionError as exc:
        raise HistoryServiceError(str(exc)) from exc


def _validate_user_id(user_id: str) -> None:
    try:
        ObjectId(user_id)
    except InvalidId as exc:
        raise HistoryServiceError("Invalid authenticated user id.") from exc


def serialize_mongo_document(document: dict) -> dict:
    return {
        "id": str(document["_id"]),
        "user_id": document["user_id"],
        "query": document["query"],
        "created_at": document["created_at"],
    }


def save_search_history(user_id: str, history_data: SearchHistoryCreate) -> dict:
    _validate_user_id(user_id)

    query = history_data.query.strip()
    collection = _history_collection()

    try:
        latest_search = collection.find_one(
            {"user_id": user_id},
            sort=[("created_at", DESCENDING)],
        )
    except PyMongoError as exc:
        raise HistoryServiceError(f"Failed to check latest search history: {exc}") from exc

    if latest_search and latest_search["query"].casefold() == query.casefold():
        return serialize_mongo_document(latest_search)

    history_document = {
        # user_id must come from the authenticated JWT user, never the frontend.
        "user_id": user_id,
        "query": query,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = collection.insert_one(history_document)
    except PyMongoError as exc:
        raise HistoryServiceError(f"Failed to save search history: {exc}") from exc

    history_document["_id"] = result.inserted_id
    return serialize_mongo_document(history_document)


def get_search_history_by_user(user_id: str) -> list[dict]:
    _validate_user_id(user_id)

    try:
        history_items = (
            _history_collection()
            .find({"user_id": user_id})
            .sort("created_at", DESCENDING)
            .limit(SEARCH_HISTORY_LIMIT)
        )
    except PyMongoError as exc:
        raise HistoryServiceError(f"Failed to fetch search history: {exc}") from exc

    return [serialize_mongo_document(item) for item in history_items]


def clear_search_history_by_user(user_id: str) -> int:
    _validate_user_id(user_id)

    try:
        result = _history_collection().delete_many({"user_id": user_id})
    except PyMongoError as exc:
        raise HistoryServiceError(f"Failed to clear search history: {exc}") from exc

    return result.deleted_count
