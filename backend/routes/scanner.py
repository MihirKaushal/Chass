"""Bounded gateway to a separately hosted model; no Torch dependency on the game API."""

import asyncio
import json
import os
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request

from backend.rate_limit import rate_limiter

router = APIRouter(prefix="/scanner", tags=["scanner"])
MAX_BYTES = 10 * 1024 * 1024
_slots = asyncio.Semaphore(2)


def service_config():
    production = os.getenv("ENVIRONMENT", "development").lower() == "production"
    url = (
        os.getenv("SCANNER_SERVICE_URL", "" if production else "http://127.0.0.1:8001")
        .strip()
        .rstrip("/")
    )
    if not url:
        return "", {}
    parsed = urlsplit(url)
    token = os.getenv("SCANNER_SERVICE_TOKEN", "").strip()
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or (production and (parsed.scheme != "https" or not token))
    ):
        raise HTTPException(503, "Scanner hosting is not configured correctly.")
    return url, ({"Authorization": f"Bearer {token}"} if token else {})


@router.get("/health")
async def health(request: Request):
    rate_limiter.check(request, "scanner-health", limit=60, window_seconds=60)
    url, headers = service_config()
    if not url:
        return {"ready": False, "configured": False}
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(65, connect=5), follow_redirects=False
        ) as client:
            response = await client.get(f"{url}/health", headers=headers)
        data = response.json() if response.status_code == 200 else {}
        ready = isinstance(data, dict) and data.get("ready") is True
    except (httpx.HTTPError, ValueError):
        ready = False
    return {"ready": ready, "configured": True, "experimental": True, "imagesStored": False}


@router.post("/scan")
async def recognize(request: Request):
    rate_limiter.check(request, "scanner-recognize", limit=40, window_seconds=3600)
    url, headers = service_config()
    if not url:
        raise HTTPException(503, "Recognition hosting is not enabled yet.")
    content_type = request.headers.get("content-type", "").split(";")[0]
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Choose a JPG, PNG, or WebP photo.")
    if _slots.locked():
        raise HTTPException(429, "The scanner is busy. Try again shortly.")
    async with _slots:
        content = bytearray()
        async for chunk in request.stream():
            if len(content) + len(chunk) > MAX_BYTES:
                raise HTTPException(413, "Choose a photo smaller than 10 MB.")
            content.extend(chunk)
        if not content:
            raise HTTPException(422, "Choose a nonempty photo.")
        try:
            async with (
                httpx.AsyncClient(timeout=75, follow_redirects=False) as client,
                client.stream(
                    "POST",
                    f"{url}/scan",
                    content=bytes(content),
                    headers={**headers, "Content-Type": content_type},
                ) as response,
            ):
                result = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(result) + len(chunk) > 2 * 1024 * 1024:
                        raise HTTPException(502, "The scanner returned an oversized response.")
                    result.extend(chunk)
                data = json.loads(result)
                if response.status_code != 200:
                    if response.status_code in {413, 415, 422, 429}:
                        detail = data.get("detail") if isinstance(data, dict) else None
                        raise HTTPException(
                            response.status_code,
                            detail
                            if isinstance(detail, str)
                            else "The scanner rejected this photo.",
                        )
                    raise HTTPException(
                        503, "Recognition is temporarily unavailable. Retry shortly."
                    )
                if not isinstance(data, dict) or not isinstance(data.get("board"), list):
                    raise HTTPException(502, "The scanner returned an invalid result.")
                return data
        except httpx.TimeoutException as error:
            raise HTTPException(
                504, "Recognition timed out. The model may be waking up; retry shortly."
            ) from error
        except (httpx.HTTPError, ValueError) as error:
            raise HTTPException(
                503, "The scanner service is unavailable. Retry shortly."
            ) from error
