from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import GoogleAuthError
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.config import get_settings
from backend.db import init_db
from backend.firebase_client import get_firestore_client, reset_firestore_client
from backend.routes import (
    bot_turn_scheduler,
    game_router,
    game_service,
    match_analysis_service,
)

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
    await match_analysis_service.start()
    try:
        yield
    finally:
        stop_event.set()
        await cleanup_task
        await bot_turn_scheduler.shutdown()
        await match_analysis_service.shutdown()


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


async def _persistence_unavailable(
    request: Request,
    error: Exception,
) -> JSONResponse:
    logger.exception(
        "Firebase persistence failed for %s %s",
        request.method,
        request.url.path,
        exc_info=error,
    )
    reset_firestore_client()
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "Game storage is temporarily unavailable. "
                "Please wait a moment and try again."
            )
        },
        headers={"Retry-After": "5"},
    )


app.add_exception_handler(GoogleAPICallError, _persistence_unavailable)
app.add_exception_handler(GoogleAuthError, _persistence_unavailable)


@app.get("/health")
def health() -> dict[str, object]:
    response = {
        "status": "ok",
        "environment": settings.environment,
        "persistence": settings.persistence_backend,
        "matchPredictor": match_analysis_service.health_status(),
        "matchPredictorEngines": match_analysis_service.health_details(),
        "classicBot": (
            "ready"
            if match_analysis_service.provider.ready
            else (
                "disabled"
                if not match_analysis_service.provider.enabled
                else "unavailable"
            )
        ),
    }
    predictor_reason = match_analysis_service.health_reason()
    if predictor_reason:
        response["matchPredictorReason"] = predictor_reason
    return response


app.include_router(game_router)
