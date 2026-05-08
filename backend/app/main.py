from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ALLOWED_ORIGINS
from app.routes.auth import router as auth_router
from app.routes.recommend import router as recommend_router

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
app.include_router(recommend_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to Project PI API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
