"""Experimental inference, hosted separately from the game API with optional token auth."""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
import secrets
import warnings
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES, MAX_PIXELS = 10 * 1024 * 1024, 24_000_000
logger = logging.getLogger(__name__)


def decode_photo(content):
    if not content or len(content) > MAX_BYTES:
        raise ValueError("Choose a nonempty image smaller than 10 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as original:
                if original.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Choose a JPG, PNG, or WebP image.")
                if original.width * original.height > MAX_PIXELS:
                    raise ValueError("Image exceeds 24 megapixels; resize it before scanning.")
                if min(original.size) < 128:
                    raise ValueError("Image is too small; use at least 128 pixels per side.")
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                return image
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise ValueError("This photo could not be decoded safely.") from error


def create_app(pipeline=None):
    origins = [
        value.strip()
        for value in os.environ.get(
            "SCANNER_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if value.strip()
    ]

    @asynccontextmanager
    async def lifespan(app):
        if (
            os.getenv("SCANNER_REQUIRE_TOKEN") == "true"
            and not os.getenv("SCANNER_SERVICE_TOKEN", "").strip()
        ):
            raise RuntimeError("Set SCANNER_SERVICE_TOKEN before exposing the inference service.")
        app.state.pipeline = pipeline
        app.state.busy = False
        if pipeline is None:
            try:
                if os.getenv("SCANNER_RUNTIME", "torch") == "onnx":
                    from .ml.onnx_inference import default_pipeline

                    app.state.pipeline = await asyncio.to_thread(default_pipeline)
                else:
                    from .ml.inference import default_pipeline

                    app.state.pipeline = await asyncio.to_thread(
                        default_pipeline, os.environ.get("SCANNER_DEVICE", "auto")
                    )
            except (OSError, ValueError, RuntimeError):
                logger.exception("Scanner model could not be loaded")
        yield
        app.state.pipeline = None

    app = FastAPI(title="Chass experimental scanner", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    def authorize(request):
        token = os.getenv("SCANNER_SERVICE_TOKEN", "").strip()
        if token and not secrets.compare_digest(
            request.headers.get("authorization", "").encode(), f"Bearer {token}".encode()
        ):
            raise HTTPException(401, "Scanner service authentication required.")

    @app.get("/ready", include_in_schema=False)
    async def ready():
        # Render's health probe cannot attach the private service token.
        if app.state.pipeline is None:
            raise HTTPException(503, "Not ready")
        return {"ready": True}

    @app.get("/health")
    async def health(request: Request):
        authorize(request)
        ready = app.state.pipeline is not None
        return {"ready": ready, "experimental": True, "imagesStored": False}

    @app.post("/scan")
    async def scan(request: Request):
        authorize(request)
        origin = request.headers.get("origin")
        if origin and origin not in origins:
            raise HTTPException(403, "This browser origin is not allowed by the scanner.")
        if request.headers.get("content-type", "").split(";")[0] not in {
            "image/jpeg",
            "image/png",
            "image/webp",
        }:
            raise HTTPException(415, "Send a JPG, PNG, or WebP photo.")
        if app.state.pipeline is None:
            raise HTTPException(
                503, "Scanner models are not loaded. Check the scanner service logs."
            )
        if app.state.busy:
            raise HTTPException(429, "A scan is already running. Please retry shortly.")
        app.state.busy = True
        try:
            content = bytearray()
            async for chunk in request.stream():
                if len(content) + len(chunk) > MAX_BYTES:
                    raise HTTPException(413, "Choose an image smaller than 10 MB.")
                content.extend(chunk)
            try:
                image = await asyncio.to_thread(decode_photo, bytes(content))
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
            if abs(image.width - image.height) > max(image.size) * 0.02:
                raise HTTPException(
                    422, "Apply Crop & Rotate to the square playing grid before scanning."
                )
            try:
                task = asyncio.create_task(
                    asyncio.to_thread(app.state.pipeline.predict, image, rectified=True)
                )
                try:
                    result = await asyncio.shield(task)
                except asyncio.CancelledError:
                    # A disconnected browser must not release the model while its thread is running.
                    await task
                    raise
                return {
                    **result,
                    "imageSha256": hashlib.sha256(content).hexdigest(),
                    "imageWidth": image.width,
                    "imageHeight": image.height,
                }
            except Exception as error:
                logger.exception("Scanner inference failed")
                raise HTTPException(
                    503, "Recognition failed. Please retry with a clear top-down photo."
                ) from error
        finally:
            app.state.busy = False

    return app


app = create_app()
