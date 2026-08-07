from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.db import init_db
from backend.firebase_client import get_firestore_client
from backend.routes import game_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().persistence_backend == "firestore":
        get_firestore_client()
    else:
        init_db()
    yield


settings = get_settings()
app = FastAPI(
    title="Chass! API",
    version="2.0.0",
    description="Customizable chess variant platform backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
        "persistence": settings.persistence_backend,
    }


app.include_router(game_router)
