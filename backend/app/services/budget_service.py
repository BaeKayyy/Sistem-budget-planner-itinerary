from __future__ import annotations

import random
from typing import Any

from ..models.budget import BudgetItem, BudgetPlannerRequest, BudgetPlannerResponse
from ..services.itinerary_service import (
    _build_candidate_pool,
    _pick_place,
    _DAY_TEMPLATE,
    _DAY_TEMPLATE_ALT,
)


def plan_budget(request: BudgetPlannerRequest) -> BudgetPlannerResponse:
    """
    Calculate an estimated budget breakdown and total cost for a trip.
    
    This simulates an itinerary generation to get realistic cost estimates
    based on the available recommendation dataset and user interests.
    """
    budget_remaining = request.budget
    used_names: set[str] = set()

    # Pre-build per-type candidate pools (reusing itinerary service logic)
    pools: dict[str, list[dict[str, Any]]] = {
        "wisata": _build_candidate_pool(request.interests, "wisata"),
        "kuliner": _build_candidate_pool(request.interests, "kuliner"),
        "cafe": _build_candidate_pool(request.interests + ["cafe"], "cafe"),
        "hotel": _build_candidate_pool(request.interests, "hotel"),
    }

    breakdown = {"wisata": 0, "kuliner": 0, "hotel": 0}
    total_cost = 0

    for day_number in range(1, request.days + 1):
        # Alternate day template to vary kuliner / cafe.
        template = _DAY_TEMPLATE if day_number % 2 != 0 else _DAY_TEMPLATE_ALT

        for place_type, _slot in template:
            pool = pools[place_type]
            # We use a large enough budget for picking to see what the 'ideal' cost would be,
            # or we use the actual remaining budget. The requirement says "estimate total costs".
            # If we use actual remaining budget, the estimate might be capped by the user's budget.
            # Usually, a budget planner should show the *actual* expected cost so the user knows if they are under or over.
            # So I'll pass a very large number for 'budget_remaining' in _pick_place to get the best match,
            # or just use the logic as is but track the overage.
            
            # To provide a realistic estimate, we pick the best matching place regardless of current budget
            # but we still track usage to avoid duplicates.
            picked = _pick_place(pool, used_names, 999_999_999) 

            if picked is None:
                continue

            name = (picked.get("name") or "").strip()
            price = picked.get("price_estimate") or 0

            # Categorize cost (mapping 'cafe' to 'kuliner' for the breakdown as per requirements)
            category = "kuliner" if place_type == "cafe" else place_type
            if category in breakdown:
                breakdown[category] += price
            
            used_names.add(name)
            total_cost += price

    # Final calculations
    remaining = request.budget - total_cost
    over_budget = total_cost > request.budget
    
    # Generate recommendations/warnings
    recommendations = []
    if over_budget:
        diff = total_cost - request.budget
        recommendations.append(f"Trip exceeds budget by Rp{diff:,}".replace(",", "."))
        recommendations.append("Consider reducing the number of days or choosing cheaper interests.")
    else:
        recommendations.append("Budget is sufficient for this trip.")
        if remaining > (request.budget * 0.2):
            recommendations.append("You have a healthy buffer for extra activities or shopping.")

    # Bonus: Estimated daily spending
    daily_spending = total_cost // request.days
    recommendations.append(f"Estimated daily spending: Rp{daily_spending:,}".replace(",", "."))

    return BudgetPlannerResponse(
        destination=request.destination,
        days=request.days,
        user_budget=request.budget,
        estimated_total_cost=total_cost,
        remaining_budget=remaining,
        over_budget=over_budget,
        breakdown=BudgetItem(**breakdown),
        recommendations=recommendations,
    )
