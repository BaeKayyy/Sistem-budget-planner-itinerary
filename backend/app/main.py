from fastapi import FastAPI

from app.routes.recommend import router as recommend_router

app = FastAPI(title="Project PI API")

app.include_router(recommend_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to Project PI API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
