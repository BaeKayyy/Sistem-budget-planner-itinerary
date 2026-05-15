from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import router as auth_router
from .itinerary import router as itinerary_router
from .recommendation import router as recommendation_router


ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app = FastAPI(title="Project PI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(recommendation_router)
app.include_router(itinerary_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to Project PI API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
