from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
)


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "wordlestack"}


@app.get("/api")
def root():
    return {"message": "Welcome to WordleStack"}


static_dir = Path("static")

if static_dir.exists():
    app.mount(
        "/",
        StaticFiles(directory=static_dir, html=True),
        name="frontend",
    )