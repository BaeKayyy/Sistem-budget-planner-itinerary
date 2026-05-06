from fastapi import FastAPI

app = FastAPI(title="Project PI API")


@app.get("/")
def read_root():
    return {"message": "Welcome to Project PI API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
