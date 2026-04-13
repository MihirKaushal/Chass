from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from backend.models.schemas import (
    CreateGameRequest,
    GameResponse,
    MoveRequest,
    ResetGameRequest,
    UpdatePiecesRequest,
    UpdateRulesRequest,
)
from backend.realtime import socket_manager
from backend.rules import RuleEngine
from backend.services.game_service import GameService

router = APIRouter(prefix="/game", tags=["game"])

rule_engine = RuleEngine()
game_service = GameService(rule_engine)


async def _broadcast(game_response: GameResponse) -> None:
    await socket_manager.broadcast(
        game_response.id,
        game_response.model_dump(by_alias=True),
    )


@router.post("/create", response_model=GameResponse)
async def create_game(request: CreateGameRequest) -> GameResponse:
    game_state = game_service.create_game(request)
    response = game_service.serialize_game(game_state)
    await _broadcast(response)
    return response


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(game_id: str) -> GameResponse:
    game_state = game_service.get_game(game_id)
    return game_service.serialize_game(game_state)


@router.post("/{game_id}/move", response_model=GameResponse)
async def make_move(game_id: str, request: MoveRequest) -> GameResponse:
    game_state, explanation = game_service.move_piece(game_id, request)
    response = game_service.serialize_game(game_state, last_explanation=explanation)
    await _broadcast(response)
    return response


@router.post("/{game_id}/rules", response_model=GameResponse)
async def update_rules(game_id: str, request: UpdateRulesRequest) -> GameResponse:
    game_state = game_service.update_rules(game_id, request)
    response = game_service.serialize_game(game_state)
    await _broadcast(response)
    return response


@router.post("/{game_id}/pieces", response_model=GameResponse)
async def update_pieces(game_id: str, request: UpdatePiecesRequest) -> GameResponse:
    game_state = game_service.update_pieces(game_id, request)
    response = game_service.serialize_game(game_state)
    await _broadcast(response)
    return response


@router.post("/{game_id}/reset", response_model=GameResponse)
async def reset_game(game_id: str, request: ResetGameRequest) -> GameResponse:
    game_state = game_service.reset_game(game_id, request)
    response = game_service.serialize_game(game_state)
    await _broadcast(response)
    return response


@router.websocket("/ws/{game_id}")
async def game_ws(websocket: WebSocket, game_id: str) -> None:
    await socket_manager.connect(game_id, websocket)

    try:
        try:
            game_state = game_service.get_game(game_id)
        except HTTPException:
            await websocket.send_json({"error": "Game not found"})
            await websocket.close(code=1008)
            return

        await websocket.send_json(
            game_service.serialize_game(game_state).model_dump(by_alias=True)
        )

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        socket_manager.disconnect(game_id, websocket)
