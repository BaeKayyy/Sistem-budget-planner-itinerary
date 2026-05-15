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
    AllocationPercent,
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
FALLBACK_POOL_SIZE = 30
RANDOM_TOP_N = 10
DEFAULT_ALLOCATION = AllocationPercent(
    hotel=30,
    wisata=25,
    kuliner=20,
    oleh_oleh=15,
    transport=10,
)
TRANSPORT_COST_PER_DAY = {
    "motor_pribadi": 25_000,
    "mobil_pribadi": 80_000,
    "ojol": 60_000,
}

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
        "people": document.get("people", 1),
        "days": document["days"],
        "estimated_total_cost": document["estimated_total_cost"],
        "budget": document["budget"],
        "allocation": document.get("allocation"),
        "allocation_percent": document.get("allocation_percent"),
        "transport_mode": document.get("transport_mode"),
        "transport_estimate": document.get("transport_estimate", 0),
        "within_budget": document["within_budget"],
        "created_at": document["created_at"],
    }


def get_allocation_percent(request: BudgetPlannerRequest | ItineraryGenerateRequest) -> AllocationPercent:
    if request.allocation_mode == "custom":
        if request.custom_allocation is None:
            raise HTTPException(status_code=422, detail="custom_allocation is required.")
        return request.custom_allocation
    return DEFAULT_ALLOCATION


def estimate_transport(days: int, transport_mode: str) -> int:
    """Static local transport estimate. No maps, fuel, toll, or live API is used."""
    return days * TRANSPORT_COST_PER_DAY.get(transport_mode, TRANSPORT_COST_PER_DAY["motor_pribadi"])


def calculate_budget_plan(
    total_budget: int,
    days: int,
    people: int,
    allocation_percent: AllocationPercent,
    transport_mode: str,
) -> dict:
    """Convert percentage allocation into nominal category budgets."""
    allocation = {
        "hotel": total_budget * allocation_percent.hotel // 100,
        "wisata": total_budget * allocation_percent.wisata // 100,
        "kuliner": total_budget * allocation_percent.kuliner // 100,
        "oleh_oleh": total_budget * allocation_percent.oleh_oleh // 100,
        "transport": total_budget * allocation_percent.transport // 100,
    }

    return {
        "budget_total": total_budget,
        "days": days,
        "people": people,
        "budget_per_day": total_budget // days,
        "budget_per_person": total_budget // (days * people),
        "allocation": allocation,
        "transport_estimate": estimate_transport(days, transport_mode),
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

    # Bigger budgets can use higher-rated places more flexibly.
    if budget_remaining >= 150_000:
        available = sorted(
            available,
            key=lambda item: (float(item.get("rating") or 0), -int(item.get("price_estimate") or 0)),
            reverse=True,
        )
    else:
        available = sorted(available, key=lambda item: int(item.get("price_estimate") or 0))

    top_candidates = available[:RANDOM_TOP_N]
    random.shuffle(top_candidates)
    available = top_candidates + available[RANDOM_TOP_N:]

    for candidate in available:
        if int(candidate.get("price_estimate") or 0) <= budget_remaining:
            return candidate

    return min(available, key=lambda item: int(item.get("price_estimate") or 0))


def generate_itinerary(user_id: str, request: ItineraryGenerateRequest) -> dict:
    allocation_percent = get_allocation_percent(request)
    budget_plan = calculate_budget_plan(
        total_budget=request.budget,
        days=request.days,
        people=request.people,
        allocation_percent=allocation_percent,
        transport_mode=request.transport_mode,
    )
    category_remaining = budget_plan["allocation"].copy()
    category_remaining["transport"] = max(
        0,
        category_remaining["transport"] - budget_plan["transport_estimate"],
    )

    total_cost = 0
    used_names: set[str] = set()
    itinerary_days: list[dict] = []

    pools = {
        place_type: build_candidate_pool(request.interests, place_type)
        for place_type, _slot in DAY_TEMPLATE
    }

    for day_number in range(1, request.days + 1):
        day_places = []
        day_cost = budget_plan["transport_estimate"] // request.days

        for place_type, _slot in DAY_TEMPLATE:
            daily_category_budget = max(0, category_remaining[place_type] // (request.days - day_number + 1))
            picked = pick_place(pools[place_type], used_names, daily_category_budget)
            if picked is None:
                continue

            name = (picked.get("name") or "").strip()
            price = int(picked.get("price_estimate") or 0)

            used_names.add(name)
            category_remaining[place_type] = max(0, category_remaining[place_type] - price)
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
        "people": request.people,
        "days": itinerary_days,
        "estimated_total_cost": total_cost,
        "budget": request.budget,
        "allocation": budget_plan["allocation"],
        "allocation_percent": allocation_percent.model_dump(),
        "transport_mode": request.transport_mode,
        "transport_estimate": budget_plan["transport_estimate"],
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
    allocation_percent = get_allocation_percent(request)
    budget_plan = calculate_budget_plan(
        total_budget=request.budget,
        days=request.days,
        people=request.people,
        allocation_percent=allocation_percent,
        transport_mode=request.transport_mode,
    )
    allocation = budget_plan["allocation"]
    transport_estimate = budget_plan["transport_estimate"]
    transport_within_budget = transport_estimate <= allocation["transport"]
    over_budget = not transport_within_budget
    remaining = request.budget - transport_estimate

    messages = [
        f"Budget per day: Rp{budget_plan['budget_per_day']:,}".replace(",", "."),
        f"Budget per person: Rp{budget_plan['budget_per_person']:,}".replace(",", "."),
        f"Transport estimate: Rp{transport_estimate:,}".replace(",", "."),
    ]

    if not transport_within_budget:
        messages.append(
            "Transport estimate exceeds the allocated transport budget."
        )
    else:
        messages.append("Budget allocation is valid and ready for itinerary generation.")

    return BudgetPlannerResponse(
        destination=request.destination,
        budget_total=request.budget,
        days=request.days,
        people=request.people,
        budget_per_day=budget_plan["budget_per_day"],
        budget_per_person=budget_plan["budget_per_person"],
        allocation_mode=request.allocation_mode,
        allocation_percent=allocation_percent,
        allocation=BudgetItem(**allocation),
        transport_mode=request.transport_mode,
        transport_estimate=transport_estimate,
        transport_within_budget=transport_within_budget,
        user_budget=request.budget,
        estimated_total_cost=transport_estimate,
        remaining_budget=remaining,
        over_budget=over_budget,
        breakdown=BudgetItem(**allocation),
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
