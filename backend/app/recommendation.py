import pickle
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, Query, status
from pymongo import DESCENDING
from pymongo.errors import PyMongoError
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.exceptions import InconsistentVersionWarning

from .auth import get_current_user
from .database import MongoDBConnectionError, get_database
from .models import (
    Favorite,
    FavoriteCreate,
    History,
    HistoryCreate,
    RecommendationResponse,
    SystemStatusResponse,
    User,
)


router = APIRouter(tags=["Recommendations"])
warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

FAVORITES_COLLECTION = "favorites"
SEARCH_HISTORY_COLLECTION = "search_history"
SEARCH_HISTORY_LIMIT = 20
VALID_TYPES = {"wisata", "kuliner", "hotel", "oleh_oleh"}
MIN_SIMILARITY_SCORE = 0.05

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR_CANDIDATES = (
    BACKEND_DIR / "data" / "processed",
    PROJECT_DIR / "data" / "processed",
)


class RecommenderLoadError(RuntimeError):
    """Raised when recommendation artifacts cannot be loaded."""


def get_data_dir() -> Path:
    for data_dir in DATA_DIR_CANDIDATES:
        if data_dir.exists():
            return data_dir

    raise RecommenderLoadError("Processed data directory was not found.")


DATA_DIR = get_data_dir()
DATASET_PATH = DATA_DIR / "tfidf_dataset.csv"
TFIDF_MATRIX_PATH = DATA_DIR / "tfidf_matrix.pkl"
VECTORIZER_PATH = DATA_DIR / "tfidf_vectorizer.pkl"
SIMILARITY_MATRIX_PATH = DATA_DIR / "cosine_similarity_matrix.pkl"


def load_pickle(path: Path, label: str):
    try:
        with path.open("rb") as file:
            return pickle.load(file)
    except FileNotFoundError as exc:
        raise RecommenderLoadError(f"{label} file was not found: {path}") from exc
    except Exception as exc:
        raise RecommenderLoadError(f"Failed to load {label}: {exc}") from exc


try:
    dataset = pd.read_csv(DATASET_PATH)
    tfidf_matrix = load_pickle(TFIDF_MATRIX_PATH, "TF-IDF matrix")
    tfidf_vectorizer = load_pickle(VECTORIZER_PATH, "TF-IDF vectorizer")
    cosine_similarity_matrix = load_pickle(SIMILARITY_MATRIX_PATH, "cosine similarity matrix")
except Exception as exc:
    raise RecommenderLoadError(f"Failed to load recommendation data: {exc}") from exc


def get_collection(name: str):
    try:
        return get_database()[name]
    except MongoDBConnectionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def normalize_query(query: str) -> str:
    """Small keyword enrichment for common PI demo queries."""
    text = query.strip().lower()
    additions = []

    if "pantai" in text:
        additions.append("beach")
    if "kopi" in text or "kafe" in text:
        additions.append("coffee cafe")
    if "oleh" in text or "souvenir" in text:
        additions.append("gift souvenir store")

    return f"{text} {' '.join(additions)}".strip()


def validate_filter_type(filter_type: str | None) -> str | None:
    if filter_type is None:
        return None

    normalized = filter_type.strip().lower()
    if normalized not in VALID_TYPES:
        options = ", ".join(sorted(VALID_TYPES))
        raise HTTPException(status_code=400, detail=f"Invalid type. Use one of: {options}")

    return normalized


def format_recommendation(row: pd.Series) -> dict:
    rating = row.get("rating")
    price = row.get("price_estimate")

    return {
        "name": row.get("name"),
        "type": row.get("type"),
        "rating": None if pd.isna(rating) else float(rating),
        "price_estimate": 0 if pd.isna(price) else int(price),
        "similarity_score": round(float(row.get("similarity_score", 0)), 4),
    }


def recommend_places(
    query: str,
    filter_type: str | None = None,
    top_k: int = 5,
    pool_size: int = 20,
    random_state: int | None = None,
) -> list[dict]:
    """Content-based recommendation with a randomized top-candidate pool."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    active_filter = validate_filter_type(filter_type)
    query_vector = tfidf_vectorizer.transform([normalize_query(query)])
    scores = cosine_similarity(query_vector, tfidf_matrix).flatten()
    scores = np.nan_to_num(scores, nan=0.0, posinf=0.0, neginf=0.0)

    results = dataset.copy()
    results["similarity_score"] = scores
    results = results[results["similarity_score"] > MIN_SIMILARITY_SCORE]

    if active_filter:
        results = results[results["type"].str.lower() == active_filter]

    results = results.sort_values("similarity_score", ascending=False)
    top_pool = results.head(max(pool_size, top_k))

    if top_pool.empty:
        return []

    if len(top_pool) > top_k:
        top_pool = top_pool.sample(n=top_k, random_state=random_state)
        top_pool = top_pool.sort_values("similarity_score", ascending=False)
    else:
        top_pool = top_pool.head(top_k)

    return [format_recommendation(row) for _, row in top_pool.iterrows()]


def serialize_favorite(document: dict) -> dict:
    return {
        "id": str(document["_id"]),
        "user_id": document["user_id"],
        "place_name": document["place_name"],
        "place_type": document["place_type"],
        "rating": document.get("rating"),
        "price_estimate": document["price_estimate"],
        "created_at": document["created_at"],
    }


def serialize_history(document: dict) -> dict:
    return {
        "id": str(document["_id"]),
        "user_id": document["user_id"],
        "query": document["query"],
        "created_at": document["created_at"],
    }


@router.get("/recommend", response_model=RecommendationResponse)
def get_recommendations(
    q: str = Query(..., min_length=1),
    filter_type: Literal["wisata", "kuliner", "hotel", "oleh_oleh"] | None = Query(
        default=None,
        alias="type",
    ),
    top_k: int = Query(default=5, ge=1, le=50),
    pool_size: int = Query(default=20, ge=5, le=100),
) -> RecommendationResponse:
    results = recommend_places(
        query=q,
        filter_type=filter_type,
        top_k=top_k,
        pool_size=pool_size,
    )

    if not results:
        raise HTTPException(status_code=404, detail="No recommendations found.")

    return RecommendationResponse(
        query=q.strip(),
        filter_type=filter_type,
        total_results=len(results),
        results=results,
    )


@router.get("/system/status", response_model=SystemStatusResponse)
def get_system_status() -> SystemStatusResponse:
    vocabulary = getattr(tfidf_vectorizer, "vocabulary_", {})
    return SystemStatusResponse(
        dataset_rows=len(dataset),
        matrix_shape=list(tfidf_matrix.shape),
        vocabulary_size=len(vocabulary),
        similarity_matrix_shape=list(cosine_similarity_matrix.shape),
    )


@router.post("/favorites", response_model=Favorite, status_code=status.HTTP_201_CREATED)
def add_favorite(
    favorite_data: FavoriteCreate,
    current_user: User = Depends(get_current_user),
) -> Favorite:
    favorite_document = {
        "user_id": current_user.id,
        "place_name": favorite_data.place_name,
        "place_type": favorite_data.place_type,
        "rating": favorite_data.rating,
        "price_estimate": favorite_data.price_estimate,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = get_collection(FAVORITES_COLLECTION).insert_one(favorite_document)
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save favorite: {exc}") from exc

    favorite_document["_id"] = result.inserted_id
    return Favorite(**serialize_favorite(favorite_document))


@router.get("/favorites", response_model=list[Favorite])
def read_favorites(current_user: User = Depends(get_current_user)) -> list[Favorite]:
    try:
        cursor = (
            get_collection(FAVORITES_COLLECTION)
            .find({"user_id": current_user.id})
            .sort("created_at", DESCENDING)
        )
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read favorites: {exc}") from exc

    return [Favorite(**serialize_favorite(item)) for item in cursor]


@router.delete("/favorites/{favorite_id}", response_model=dict[str, str])
def remove_favorite(
    favorite_id: str = ApiPath(...),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    try:
        object_id = ObjectId(favorite_id)
    except InvalidId as exc:
        raise HTTPException(status_code=404, detail="Favorite was not found.") from exc

    try:
        result = get_collection(FAVORITES_COLLECTION).delete_one(
            {"_id": object_id, "user_id": current_user.id}
        )
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete favorite: {exc}") from exc

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favorite was not found.")

    return {"message": "Favorite deleted successfully."}


@router.post("/history", response_model=History, status_code=status.HTTP_201_CREATED)
def create_search_history(
    history_data: HistoryCreate,
    current_user: User = Depends(get_current_user),
) -> History:
    collection = get_collection(SEARCH_HISTORY_COLLECTION)
    query = history_data.query.strip()

    try:
        latest = collection.find_one(
            {"user_id": current_user.id},
            sort=[("created_at", DESCENDING)],
        )
        if latest and latest["query"].casefold() == query.casefold():
            return History(**serialize_history(latest))

        history_document = {
            "user_id": current_user.id,
            "query": query,
            "created_at": datetime.now(timezone.utc),
        }
        result = collection.insert_one(history_document)
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save history: {exc}") from exc

    history_document["_id"] = result.inserted_id
    return History(**serialize_history(history_document))


@router.get("/history", response_model=list[History])
def read_search_history(current_user: User = Depends(get_current_user)) -> list[History]:
    try:
        cursor = (
            get_collection(SEARCH_HISTORY_COLLECTION)
            .find({"user_id": current_user.id})
            .sort("created_at", DESCENDING)
            .limit(SEARCH_HISTORY_LIMIT)
        )
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read history: {exc}") from exc

    return [History(**serialize_history(item)) for item in cursor]


@router.delete("/history", response_model=dict[str, str | int])
def clear_search_history(current_user: User = Depends(get_current_user)) -> dict[str, str | int]:
    try:
        result = get_collection(SEARCH_HISTORY_COLLECTION).delete_many(
            {"user_id": current_user.id}
        )
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to clear history: {exc}") from exc

    return {
        "message": "Search history cleared successfully.",
        "deleted_count": result.deleted_count,
    }
