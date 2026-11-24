from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException
from starlette.requests import HTTPConnection

# Longest window any caller uses; idle keys older than this are discarded.
MAX_WINDOW_SECONDS = 3600
SWEEP_EVERY_CHECKS = 1024


def trusted_proxy_hops() -> int:
    """Number of reverse proxies in front of the app that append to X-Forwarded-For."""
    try:
        return max(0, int(os.getenv("TRUSTED_PROXY_HOPS", "0")))
    except ValueError:
        return 0


def client_address(connection: HTTPConnection) -> str:
    """Resolve the caller's address without trusting client-supplied header entries.

    Proxies such as Render's append the address they observed to X-Forwarded-For
    and keep anything the client sent, so entries are read from the right. With
    N trusted hops, the Nth entry from the right is the address the outermost
    trusted proxy saw. Without trusted hops the socket peer is used.
    """
    peer = connection.client.host if connection.client else "unknown"
    hops = trusted_proxy_hops()
    if hops == 0:
        return peer
    forwarded = [
        entry.strip()
        for header in connection.headers.getlist("x-forwarded-for")
        for entry in header.split(",")
        if entry.strip()
    ]
    if len(forwarded) < hops:
        return peer
    return forwarded[-hops]


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._checks = 0

    def check(
        self,
        request: HTTPConnection,
        bucket: str,
        *,
        limit: int,
        window_seconds: int,
        discriminator: str = "",
    ) -> None:
        key = f"{bucket}:{client_address(request)}:{discriminator}"
        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            self._checks += 1
            if self._checks % SWEEP_EVERY_CHECKS == 0:
                self._sweep(now)

            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please wait before trying again.",
                    headers={"Retry-After": str(retry_after)},
                )

            events.append(now)

    def _sweep(self, now: float) -> None:
        stale_before = now - MAX_WINDOW_SECONDS
        stale = [
            key
            for key, events in self._events.items()
            if not events or events[-1] <= stale_before
        ]
        for key in stale:
            del self._events[key]

    def tracked_keys(self) -> int:
        with self._lock:
            return len(self._events)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._checks = 0


rate_limiter = SlidingWindowRateLimiter()
