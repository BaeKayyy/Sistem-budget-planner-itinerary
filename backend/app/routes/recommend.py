from fastapi import APIRouter
from app.services.recommender import recommend_places

router = APIRouter()

@router.get("/recommend")
def recommend(q: str, type: str = None):
    results = recommend_places(q, filter_type=type)
    return results.to_dict(orient="records")