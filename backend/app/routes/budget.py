from fastapi import APIRouter, Depends, status

from ..models.budget import BudgetPlannerRequest, BudgetPlannerResponse
from ..models.user import UserResponse
from ..services.budget_service import plan_budget
from .auth import get_current_user

router = APIRouter(
    prefix="/budget",
    tags=["Budget Planner"],
)


@router.post(
    "/plan",
    response_model=BudgetPlannerResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate estimated budget plan",
    description=(
        "Analyze trip costs and generate a professional budget breakdown. "
        "This endpoint simulates a personalized trip based on the provided "
        "destination, duration, and interests to estimate realistic expenses "
        "for sightseeing, food, and accommodation.\n\n"
        "**Key features:**\n"
        "- Smart validation of over-budget trips\n"
        "- Cost breakdown by category (wisata, kuliner, hotel)\n"
        "- Personalized recommendations based on remaining budget\n"
        "- Estimated daily spending calculation"
    ),
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
                        "destination": "Yogyakarta",
                        "days": 2,
                        "budget": 500000,
                        "interests": ["pantai", "kuliner", "hotel"]
                    }
                }
            }
        }
    },
)
def plan_budget_endpoint(
    request: BudgetPlannerRequest,
    current_user: UserResponse = Depends(get_current_user),
) -> BudgetPlannerResponse:
    """
    Generate an estimated budget plan.
    
    The user_id from the authenticated JWT is used to ensure the request is 
    valid, though for this specific simulation, the user identity doesn't 
    affect the calculation logic itself.
    """
    return plan_budget(request)
