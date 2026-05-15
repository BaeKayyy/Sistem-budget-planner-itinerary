import math
import random
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from .auth import get_current_user
from .database import MongoDBConnectionError, get_database
from .models import (
    BudgetItem,
    BudgetPlannerRequest,
    BudgetPlannerResponse,
    Itinerary,
    ItineraryGenerateRequest,
    User,
)
from .recommendation import dataset, recommend_places


router = APIRouter(tags=["Itinerary and Budget"])

ITINERARIES_COLLECTION = "itineraries"
TRANSPORT_PER_DAY = 30_000
FALLBACK_POOL_SIZE = 30
RANDOM_TOP_N = 10

# Simple PI-friendly daily travel pattern.
DAY_TEMPLATE = [
    ("wisata", "morning"),
    ("kuliner", "afternoon"),
    ("oleh_oleh", "souvenir"),
    ("hotel", "evening"),
]


def itineraries_collection():
    try:
        return get_database()[ITINERARIES_COLLECTION]
    except MongoDBConnectionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def is_nan(value: Any) -> bool:
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def serialize_itinerary(document: dict) -> dict:
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


def estimate_transport(days: int) -> int:
    """Static local transport estimate. No live transport API is used."""
    return days * TRANSPORT_PER_DAY


def allocate_budget(total_budget: int) -> dict[str, int]:
    """Simple custom budget allocation by category."""
    return {
        "wisata": int(total_budget * 0.20),
        "kuliner": int(total_budget * 0.25),
        "oleh_oleh": int(total_budget * 0.15),
        "hotel": int(total_budget * 0.30),
        "transport": int(total_budget * 0.10),
    }


def fallback_candidates(place_type: str) -> list[dict]:
    df = dataset[dataset["type"].str.lower() == place_type].copy()
    if df.empty:
        return []

    df = df.sample(min(FALLBACK_POOL_SIZE, len(df)))
    candidates = []
    for _, row in df.iterrows():
        candidates.append(
            {
                "name": row.get("name"),
                "type": row.get("type"),
                "rating": None if is_nan(row.get("rating")) else float(row.get("rating")),
                "price_estimate": 0
                if is_nan(row.get("price_estimate"))
                else int(row.get("price_estimate")),
            }
        )
    return candidates


def build_candidate_pool(interests: list[str], place_type: str) -> list[dict]:
    """Use recommendation results first, then dataset fallback."""
    queries = interests or [place_type]
    if place_type == "oleh_oleh":
        queries = queries + ["oleh oleh souvenir"]

    seen_names: set[str] = set()
    pool: list[dict] = []

    for query in queries:
        try:
            candidates = recommend_places(
                query=query,
                filter_type=place_type,
                top_k=10,
                pool_size=30,
            )
        except HTTPException:
            candidates = []

        for candidate in candidates:
            name = (candidate.get("name") or "").strip()
            if name and name not in seen_names:
                seen_names.add(name)
                pool.append(candidate)

    for candidate in fallback_candidates(place_type):
        name = (candidate.get("name") or "").strip()
        if name and name not in seen_names:
            seen_names.add(name)
            pool.append(candidate)

    return pool


def pick_place(pool: list[dict], used_names: set[str], budget_remaining: int) -> dict | None:
    """Pick one unused place with light randomization from the top candidates."""
    available = [item for item in pool if (item.get("name") or "").strip() not in used_names]
    if not available:
        return None

    top_candidates = available[:RANDOM_TOP_N]
    random.shuffle(top_candidates)
    available = top_candidates + available[RANDOM_TOP_N:]

    for candidate in available:
        if int(candidate.get("price_estimate") or 0) <= budget_remaining:
            return candidate

    return min(available, key=lambda item: int(item.get("price_estimate") or 0))


def generate_itinerary(user_id: str, request: ItineraryGenerateRequest) -> dict:
    budget_remaining = request.budget
    total_cost = 0
    used_names: set[str] = set()
    itinerary_days: list[dict] = []

    pools = {
        place_type: build_candidate_pool(request.interests, place_type)
        for place_type, _slot in DAY_TEMPLATE
    }

    for day_number in range(1, request.days + 1):
        day_places = []
        day_cost = TRANSPORT_PER_DAY

        for place_type, _slot in DAY_TEMPLATE:
            picked = pick_place(pools[place_type], used_names, budget_remaining)
            if picked is None:
                continue

            name = (picked.get("name") or "").strip()
            price = int(picked.get("price_estimate") or 0)

            used_names.add(name)
            budget_remaining = max(0, budget_remaining - price)
            day_cost += price

            day_places.append(
                {
                    "name": name,
                    "type": picked.get("type") or place_type,
                    "price_estimate": price,
                    "rating": picked.get("rating"),
                }
            )

        total_cost += day_cost
        itinerary_days.append(
            {
                "day": day_number,
                "places": day_places,
                "day_cost": day_cost,
            }
        )

    document = {
        "user_id": user_id,
        "destination": request.destination,
        "days": itinerary_days,
        "estimated_total_cost": total_cost,
        "budget": request.budget,
        "within_budget": total_cost <= request.budget,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = itineraries_collection().insert_one(document)
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save itinerary: {exc}") from exc

    document["_id"] = result.inserted_id
    return serialize_itinerary(document)


def get_itineraries_by_user(user_id: str) -> list[dict]:
    try:
        cursor = (
            itineraries_collection()
            .find({"user_id": user_id})
            .sort("created_at", DESCENDING)
        )
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read itineraries: {exc}") from exc

    return [serialize_itinerary(item) for item in cursor]


def delete_itinerary(user_id: str, itinerary_id: str) -> None:
    try:
        object_id = ObjectId(itinerary_id)
    except InvalidId as exc:
        raise HTTPException(status_code=404, detail="Itinerary not found.") from exc

    try:
        result = itineraries_collection().delete_one(
            {"_id": object_id, "user_id": user_id}
        )
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete itinerary: {exc}") from exc

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Itinerary not found.")


def plan_budget(request: BudgetPlannerRequest) -> BudgetPlannerResponse:
    used_names: set[str] = set()
    budget_plan = allocate_budget(request.budget)
    breakdown = {
        "wisata": 0,
        "kuliner": 0,
        "oleh_oleh": 0,
        "hotel": 0,
        "transport": estimate_transport(request.days),
    }

    pools = {
        place_type: build_candidate_pool(request.interests, place_type)
        for place_type, _slot in DAY_TEMPLATE
    }

    for _day_number in range(1, request.days + 1):
        for place_type, _slot in DAY_TEMPLATE:
            picked = pick_place(pools[place_type], used_names, 999_999_999)
            if picked is None:
                continue

            name = (picked.get("name") or "").strip()
            used_names.add(name)
            breakdown[place_type] += int(picked.get("price_estimate") or 0)

    total_cost = sum(breakdown.values())
    remaining = request.budget - total_cost
    over_budget = total_cost > request.budget

    messages = [
        f"Estimated transport cost: Rp{breakdown['transport']:,}".replace(",", "."),
        f"Suggested hotel allocation: Rp{budget_plan['hotel']:,}".replace(",", "."),
    ]
    if over_budget:
        messages.append(
            f"Trip exceeds budget by Rp{abs(remaining):,}".replace(",", ".")
        )
        messages.append("Consider reducing days or selecting cheaper categories.")
    else:
        messages.append("Budget is sufficient for this trip.")

    return BudgetPlannerResponse(
        destination=request.destination,
        days=request.days,
        user_budget=request.budget,
        estimated_total_cost=total_cost,
        remaining_budget=remaining,
        over_budget=over_budget,
        breakdown=BudgetItem(**breakdown),
        recommendations=messages,
    )


@router.post(
    "/itinerary/generate",
    response_model=Itinerary,
    status_code=status.HTTP_201_CREATED,
)
def generate_itinerary_endpoint(
    request: ItineraryGenerateRequest,
    current_user: User = Depends(get_current_user),
) -> Itinerary:
    itinerary = generate_itinerary(current_user.id, request)
    return Itinerary(**itinerary)


@router.get("/itinerary", response_model=list[Itinerary])
def list_itineraries(current_user: User = Depends(get_current_user)) -> list[Itinerary]:
    return [Itinerary(**item) for item in get_itineraries_by_user(current_user.id)]


@router.delete("/itinerary/{itinerary_id}", response_model=dict[str, str])
def delete_itinerary_endpoint(
    itinerary_id: str = Path(...),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    delete_itinerary(current_user.id, itinerary_id)
    return {"message": "Itinerary deleted successfully."}


@router.post(
    "/budget/plan",
    response_model=BudgetPlannerResponse,
    status_code=status.HTTP_200_OK,
)
def plan_budget_endpoint(
    request: BudgetPlannerRequest,
    current_user: User = Depends(get_current_user),
) -> BudgetPlannerResponse:
    # current_user proves the request is authenticated; calculations use request data.
    return plan_budget(request)
