from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.db import init_db
from backend.firebase_client import get_firestore_client
from backend.routes import game_router, game_service

logger = logging.getLogger(__name__)


async def _cleanup_inactive_games() -> None:
    try:
        deleted = await asyncio.to_thread(game_service.cleanup_inactive_games)
        if deleted:
            logger.info("Deleted %s inactive game(s)", deleted)
    except Exception:
        # Cleanup is retried on the next interval and must not take down active games.
        logger.exception("Inactive-game cleanup failed")


async def _cleanup_loop(stop_event: asyncio.Event, interval_seconds: int) -> None:
    await _cleanup_inactive_games()
    while True:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            return
        except TimeoutError:
            await _cleanup_inactive_games()


@asynccontextmanager
async def lifespan(_: FastAPI):
    current_settings = get_settings()
    if current_settings.persistence_backend == "firestore":
        get_firestore_client()
    else:
        init_db()

    stop_event = asyncio.Event()
    cleanup_task = asyncio.create_task(
        _cleanup_loop(
            stop_event,
            current_settings.game_cleanup_interval_minutes * 60,
        )
    )
    try:
        yield
    finally:
        stop_event.set()
        await cleanup_task


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
