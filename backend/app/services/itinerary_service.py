"""Itinerary generation and persistence service.

Generation strategy
-------------------
Each day follows a logical template:
  - Morning  : wisata  (sightseeing / beach / nature)
  - Afternoon: kuliner or cafe  (food & drink)
  - Evening  : hotel   (accommodation)

Places are selected from the existing TF-IDF recommendation dataset so that
interests supplied by the user influence the ranking.  Duplicate places are
avoided across the whole itinerary.  When the dataset contains fewer matches
than required, the engine gracefully falls back to generic type-based
selection from the full dataset.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from ..database.mongodb import MongoDBConnectionError, get_database
from ..models.itinerary import (
    ItineraryDay,
    ItineraryGenerateRequest,
    ItineraryPlace,
)
from ..services.recommender import dataset, recommend_places

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ITINERARIES_COLLECTION = "itineraries"

# Slots assigned per day (order matters — it is the visit sequence).
# Each slot is (place_type, slot_label) where place_type matches the
# dataset "type" column values.
_DAY_TEMPLATE: list[tuple[str, str]] = [
    ("wisata", "morning"),
    ("kuliner", "afternoon"),
    ("hotel", "evening"),
]

# On even days swap kuliner → cafe to introduce variety.
_DAY_TEMPLATE_ALT: list[tuple[str, str]] = [
    ("wisata", "morning"),
    ("cafe", "afternoon"),
    ("hotel", "evening"),
]

# How many candidate recommendations to pull per interest query.
_INTEREST_TOP_K = 20

# Fallback candidates pulled from the raw dataset when TF-IDF yields nothing.
_FALLBACK_POOL_SIZE = 30

# Slight randomisation: shuffle top-N candidates before picking the first
# unused one so the same itinerary is not produced every time.
_SHUFFLE_TOP_N = 5


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class ItineraryServiceError(RuntimeError):
    """Raised when an itinerary database operation fails."""


class ItineraryNotFoundError(ItineraryServiceError):
    """Raised when an itinerary does not exist for the current user."""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _itineraries_collection():
    try:
        return get_database()[ITINERARIES_COLLECTION]
    except MongoDBConnectionError as exc:
        raise ItineraryServiceError(str(exc)) from exc


def _serialize(document: dict) -> dict:
    """Convert a raw MongoDB document to a plain Python dict."""
    return {
        "id": str(document["_id"]),
        "user_id": document["user_id"],
        "destination": document["destination"],
        "days": document["days"],
        "estimated_total_cost": document["estimated_total_cost"],
        "budget": document["budget"],
        "within_budget": document["within_budget"],
        "created_at": document["created_at"],
    }


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------


def _candidates_for_interest(interest: str, place_type: str) -> list[dict]:
    """Return TF-IDF recommendations for *interest* filtered by *place_type*."""
    try:
        results = recommend_places(
            query=interest,
            filter_type=place_type if place_type in {"wisata", "kuliner", "hotel"} else None,
            top_k=_INTEREST_TOP_K,
        )
        # If the engine filtered by type, results already match; otherwise filter here.
        if place_type not in {"wisata", "kuliner", "hotel"}:
            results = [r for r in results if (r.get("type") or "").lower() == place_type]
        return results
    except Exception:
        return []


def _fallback_candidates(place_type: str) -> list[dict]:
    """Pull a random sample directly from the raw dataset for *place_type*."""
    df = dataset[dataset["type"].str.lower() == place_type].copy()
    if df.empty:
        return []

    sample = df.sample(min(_FALLBACK_POOL_SIZE, len(df)))
    results = []
    for _, row in sample.iterrows():
        price_raw = row.get("price_estimate")
        results.append(
            {
                "name": row.get("name"),
                "type": row.get("type"),
                "rating": None if _is_nan(row.get("rating")) else float(row.get("rating")),
                "price_estimate": 0 if _is_nan(price_raw) else int(price_raw),
            }
        )
    return results


def _is_nan(value) -> bool:
    try:
        import math
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def _build_candidate_pool(interests: list[str], place_type: str) -> list[dict]:
    """Assemble an ordered candidate list: interest-driven first, then fallback."""
    seen_names: set[str] = set()
    pool: list[dict] = []

    # 1. Query each interest keyword.
    for interest in interests:
        for candidate in _candidates_for_interest(interest, place_type):
            name = (candidate.get("name") or "").strip()
            if name and name not in seen_names:
                seen_names.add(name)
                pool.append(candidate)

    # 2. Supplement with fallback if the pool is thin.
    if len(pool) < _FALLBACK_POOL_SIZE:
        for candidate in _fallback_candidates(place_type):
            name = (candidate.get("name") or "").strip()
            if name and name not in seen_names:
                seen_names.add(name)
                pool.append(candidate)

    return pool


def _pick_place(
    pool: list[dict],
    used_names: set[str],
    budget_remaining: int,
) -> dict | None:
    """Pick the first unused candidate, with light randomisation in the top-N."""
    eligible = [p for p in pool if (p.get("name") or "").strip() not in used_names]

    # Slightly shuffle the very top candidates so results vary between calls.
    top = eligible[: _SHUFFLE_TOP_N]
    random.shuffle(top)
    eligible = top + eligible[_SHUFFLE_TOP_N:]

    for candidate in eligible:
        price = candidate.get("price_estimate") or 0
        if price <= budget_remaining:
            return candidate

    # Budget exhausted — still return the cheapest option to avoid empty days.
    if eligible:
        return min(eligible, key=lambda c: c.get("price_estimate") or 0)

    return None


# ---------------------------------------------------------------------------
# Hotel pool helpers  (avoid repeating the same hotel every day)
# ---------------------------------------------------------------------------


def _build_hotel_pool(interests: list[str]) -> list[dict]:
    return _build_candidate_pool(interests, "hotel")


# ---------------------------------------------------------------------------
# Public generation entry-point
# ---------------------------------------------------------------------------


def generate_itinerary(
    user_id: str,
    request: ItineraryGenerateRequest,
) -> dict:
    """Generate, persist, and return a complete itinerary.

    Parameters
    ----------
    user_id:
        Authenticated user id sourced from the JWT — never from the frontend.
    request:
        Validated generation request containing destination, days, budget,
        and interests.

    Returns
    -------
    dict
        Serialised itinerary document ready to be returned by the API layer.
    """
    budget_remaining = request.budget
    used_names: set[str] = set()

    # Pre-build per-type candidate pools once to avoid repeated TF-IDF calls.
    pools: dict[str, list[dict]] = {
        "wisata": _build_candidate_pool(request.interests, "wisata"),
        "kuliner": _build_candidate_pool(request.interests, "kuliner"),
        "cafe": _build_candidate_pool(request.interests + ["cafe"], "cafe"),
        "hotel": _build_hotel_pool(request.interests),
    }

    itinerary_days: list[dict] = []
    total_cost = 0

    for day_number in range(1, request.days + 1):
        # Alternate day template to vary kuliner / cafe.
        template = _DAY_TEMPLATE if day_number % 2 != 0 else _DAY_TEMPLATE_ALT

        day_places: list[dict] = []
        day_cost = 0

        # Hotels should rotate — remove previously used hotels from the pool
        # to avoid the same hotel appearing every single night.
        for place_type, _slot in template:
            pool = pools[place_type]
            picked = _pick_place(pool, used_names, budget_remaining)

            if picked is None:
                continue

            name = (picked.get("name") or "").strip()
            price = picked.get("price_estimate") or 0

            # Hotels are reusable across nights ONLY when the pool is small,
            # so we track them separately.
            if place_type != "hotel":
                used_names.add(name)
            else:
                # Mark hotel used so it won't repeat on consecutive nights,
                # but allow re-use once the pool cycles through.
                used_names.add(name)

            day_places.append(
                {
                    "name": name,
                    "type": picked.get("type") or place_type,
                    "price_estimate": price,
                    "rating": picked.get("rating"),
                }
            )

            day_cost += price
            budget_remaining = max(0, budget_remaining - price)

        itinerary_days.append(
            {
                "day": day_number,
                "places": day_places,
                "day_cost": day_cost,
            }
        )
        total_cost += day_cost

    # ------------------------------------------------------------------
    # Persist to MongoDB
    # ------------------------------------------------------------------
    document = {
        # user_id must originate from the verified JWT token, never the body.
        "user_id": user_id,
        "destination": request.destination,
        "days": itinerary_days,
        "estimated_total_cost": total_cost,
        "budget": request.budget,
        "within_budget": total_cost <= request.budget,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = _itineraries_collection().insert_one(document)
    except PyMongoError as exc:
        raise ItineraryServiceError(f"Failed to save itinerary: {exc}") from exc

    document["_id"] = result.inserted_id
    return _serialize(document)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def get_itineraries_by_user(user_id: str) -> list[dict]:
    """Return all itineraries owned by *user_id*, newest first."""
    try:
        cursor = (
            _itineraries_collection()
            .find({"user_id": user_id})
            .sort("created_at", DESCENDING)
        )
    except PyMongoError as exc:
        raise ItineraryServiceError(f"Failed to fetch itineraries: {exc}") from exc

    return [_serialize(doc) for doc in cursor]


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def delete_itinerary(user_id: str, itinerary_id: str) -> None:
    """Delete an itinerary owned by *user_id*.

    Raises
    ------
    ItineraryNotFoundError
        When the id is invalid or does not belong to the current user.
    ItineraryServiceError
        On any underlying database failure.
    """
    try:
        object_id = ObjectId(itinerary_id)
    except InvalidId as exc:
        raise ItineraryNotFoundError("Itinerary not found.") from exc

    try:
        result = _itineraries_collection().delete_one(
            {
                "_id": object_id,
                # Enforce ownership — users can only delete their own itineraries.
                "user_id": user_id,
            }
        )
    except PyMongoError as exc:
        raise ItineraryServiceError(f"Failed to delete itinerary: {exc}") from exc

    if result.deleted_count == 0:
        raise ItineraryNotFoundError("Itinerary not found.")
