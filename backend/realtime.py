from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class GameSocketManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, game_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[game_id].add(websocket)

    def disconnect(self, game_id: str, websocket: WebSocket) -> None:
        if game_id not in self.connections:
            return
        self.connections[game_id].discard(websocket)
        if not self.connections[game_id]:
            self.connections.pop(game_id, None)

    async def broadcast(self, game_id: str, payload: dict) -> None:
        if game_id not in self.connections:
            return

        dead_sockets: list[WebSocket] = []
        for websocket in self.connections[game_id]:
            try:
                await websocket.send_json(payload)
            except Exception:
                dead_sockets.append(websocket)

        for websocket in dead_sockets:
            self.disconnect(game_id, websocket)


socket_manager = GameSocketManager()
