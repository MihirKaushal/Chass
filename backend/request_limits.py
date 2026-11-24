"""Reject oversized request bodies before they are parsed."""

from __future__ import annotations

import json

# Game requests are small JSON documents; the largest legitimate payload (a full
# 16x16 custom layout with every setting) is well under 64 KiB.
MAX_JSON_BODY_BYTES = 256 * 1024
# The scanner upload streams its own body and enforces a separate 10 MB cap.
STREAMED_UPLOAD_PATHS = frozenset({"/scanner/scan"})

_TOO_LARGE_BODY = json.dumps({"detail": "This request is too large."}).encode()


class RequestSizeLimitMiddleware:
    def __init__(self, app, max_bytes: int = MAX_JSON_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["path"] in STREAMED_UPLOAD_PATHS:
            await self.app(scope, receive, send)
            return

        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared is not None:
            try:
                too_large = int(declared) > self.max_bytes
            except ValueError:
                too_large = False
            if too_large:
                await self._reject(send)
                return

        # Bodies without a reliable Content-Length (chunked uploads) are counted
        # as they arrive. Once the limit is crossed, whatever the application
        # tries to send is replaced by a single 413 response.
        received = 0
        overflowed = False
        rejected = False

        async def counted_receive():
            nonlocal received, overflowed
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    overflowed = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            nonlocal rejected
            if not overflowed:
                await send(message)
            elif not rejected and message["type"] == "http.response.start":
                rejected = True
                await self._reject(send)

        try:
            await self.app(scope, counted_receive, guarded_send)
        except Exception:
            # Truncating the body can make parsing fail; that is the rejection.
            if not overflowed:
                raise
        if overflowed and not rejected:
            await self._reject(send)

    @staticmethod
    async def _reject(send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_TOO_LARGE_BODY)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _TOO_LARGE_BODY})
