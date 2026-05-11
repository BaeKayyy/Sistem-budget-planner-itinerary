from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import ALLOWED_ORIGINS
from .routes.auth import router as auth_router
from .routes.favorites import router as favorites_router
from .routes.history import router as history_router
from .routes.itinerary import router as itinerary_router
from .routes.recommend import router as recommend_router
from .routes.budget import router as budget_router

app = FastAPI(title="Project PI API")

# CORS allows the React frontend running on port 3000 to call this FastAPI API.
# Keep allowed origins explicit so browser access is predictable and controlled.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(favorites_router)
app.include_router(history_router)
app.include_router(recommend_router)
app.include_router(itinerary_router)
app.include_router(budget_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to Project PI API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
