from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from fastapi import WebSocket


@dataclass(frozen=True)
class SocketIdentity:
    color: str | None
    role: str


class GameSocketManager:
    def __init__(self) -> None:
        self.connections: dict[str, dict[WebSocket, SocketIdentity]] = defaultdict(dict)

    async def connect(
        self,
        game_id: str,
        websocket: WebSocket,
        identity: SocketIdentity,
        *,
        accept: bool = True,
    ) -> None:
        if accept:
            await websocket.accept()
        self.connections[game_id][websocket] = identity

    def disconnect(self, game_id: str, websocket: WebSocket) -> None:
        room = self.connections.get(game_id)
        if room is None:
            return
        room.pop(websocket, None)
        if not room:
            self.connections.pop(game_id, None)

    async def send(self, websocket: WebSocket, event_type: str, payload: dict | None = None) -> None:
        await websocket.send_json({"type": event_type, **(payload or {})})

    async def broadcast(self, game_id: str, event_type: str, payload: dict | None = None) -> None:
        room = self.connections.get(game_id)
        if not room:
            return

        message = {"type": event_type, **(payload or {})}
        sockets = list(room)
        results = await asyncio.gather(
            *(websocket.send_json(message) for websocket in sockets),
            return_exceptions=True,
        )
        dead_sockets = [
            websocket
            for websocket, result in zip(sockets, results, strict=True)
            if isinstance(result, Exception)
        ]

        for websocket in dead_sockets:
            self.disconnect(game_id, websocket)

    async def broadcast_personalized(
        self,
        game_id: str,
        event_type: str,
        payload_for_identity: Callable[[SocketIdentity], dict],
        identity_filter: Callable[[SocketIdentity], bool] | None = None,
    ) -> None:
        room = self.connections.get(game_id)
        if not room:
            return

        deliveries = []
        dead_sockets: list[WebSocket] = []
        for websocket, identity in list(room.items()):
            if identity_filter is not None and not identity_filter(identity):
                continue
            try:
                deliveries.append(
                    (
                        websocket,
                        {"type": event_type, **payload_for_identity(identity)},
                    )
                )
            except Exception:
                dead_sockets.append(websocket)

        results = await asyncio.gather(
            *(websocket.send_json(message) for websocket, message in deliveries),
            return_exceptions=True,
        )
        dead_sockets.extend(
            websocket
            for (websocket, _), result in zip(deliveries, results, strict=True)
            if isinstance(result, Exception)
        )

        for websocket in dead_sockets:
            self.disconnect(game_id, websocket)

    async def broadcast_presence(self, game_id: str) -> None:
        room = self.connections.get(game_id, {})
        colors = {
            identity.color
            for identity in room.values()
            if identity.color in {"white", "black"}
        }
        await self.broadcast(
            game_id,
            "presence",
            {
                "connected": {
                    "white": "white" in colors,
                    "black": "black" in colors,
                },
                "connectionCount": len(room),
            },
        )


socket_manager = GameSocketManager()
