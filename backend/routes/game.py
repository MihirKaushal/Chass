from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from backend.models.schemas import (
    CreateGameRequest,
    GameResponse,
    GameSessionResponse,
    InviteResponse,
    JoinGameRequest,
    MoveRequest,
    ResetGameRequest,
    UpdateBoardLayoutRequest,
    UpdatePiecesRequest,
    UpdateRulesRequest,
)
from backend.rate_limit import rate_limiter
from backend.realtime import SocketIdentity, socket_manager
from backend.rules import RuleEngine
from backend.services.game_service import GameService

router = APIRouter(prefix="/game", tags=["game"])
rule_engine = RuleEngine()
game_service = GameService(rule_engine)


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, separator, token = authorization.partition(" ")
    if separator and scheme.lower() == "bearer" and token.strip():
        return token.strip()
    raise HTTPException(status_code=401, detail="Authorization must use a Bearer token")


async def _broadcast_state(game_response: GameResponse) -> None:
    await socket_manager.broadcast(
        game_response.id,
        "game_state",
        {"game": game_response.model_dump(by_alias=True)},
    )


@router.post("/create", response_model=GameSessionResponse)
async def create_game(payload: CreateGameRequest, request: Request) -> GameSessionResponse:
    rate_limiter.check(request, "create", limit=20, window_seconds=3600)
    return await run_in_threadpool(game_service.create_game, payload)


@router.post("/join", response_model=GameSessionResponse)
async def join_game(payload: JoinGameRequest, request: Request) -> GameSessionResponse:
    rate_limiter.check(request, "join", limit=30, window_seconds=60)
    response = await run_in_threadpool(game_service.join_game, payload)
    await socket_manager.broadcast(
        response.game.id,
        "player_joined",
        {"color": response.playerColor},
    )
    await _broadcast_state(response.game)
    await socket_manager.broadcast_presence(response.game.id)
    return response


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(
    game_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    record = await run_in_threadpool(
        game_service.get_game,
        game_id,
        _bearer_token(authorization),
    )
    return game_service.serialize_game(record)


@router.post("/{game_id}/move", response_model=GameResponse)
async def make_move(
    game_id: str,
    payload: MoveRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    rate_limiter.check(
        request,
        "move",
        limit=120,
        window_seconds=60,
        discriminator=game_id,
    )
    record, explanation = await run_in_threadpool(
        game_service.move_piece,
        game_id,
        payload,
        _bearer_token(authorization),
    )
    response = game_service.serialize_game(record, last_explanation=explanation)
    await _broadcast_state(response)
    if response.gameStatus in {"checkmate", "stalemate", "score_target"}:
        await socket_manager.broadcast(
            response.id,
            "game_ended",
            {"game": response.model_dump(by_alias=True)},
        )
    return response


@router.post("/{game_id}/rules", response_model=GameResponse)
async def update_rules(
    game_id: str,
    request: UpdateRulesRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    record = await run_in_threadpool(
        game_service.update_rules,
        game_id,
        request,
        _bearer_token(authorization),
    )
    response = game_service.serialize_game(record)
    await _broadcast_state(response)
    return response


@router.post("/{game_id}/pieces", response_model=GameResponse)
async def update_pieces(
    game_id: str,
    request: UpdatePiecesRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    record = await run_in_threadpool(
        game_service.update_pieces,
        game_id,
        request,
        _bearer_token(authorization),
    )
    response = game_service.serialize_game(record)
    await _broadcast_state(response)
    return response


@router.post("/{game_id}/layout", response_model=GameResponse)
async def update_board_layout(
    game_id: str,
    request: UpdateBoardLayoutRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    record = await run_in_threadpool(
        game_service.update_board_layout,
        game_id,
        request,
        _bearer_token(authorization),
    )
    response = game_service.serialize_game(record)
    await _broadcast_state(response)
    return response


@router.post("/{game_id}/reset", response_model=GameResponse)
async def reset_game(
    game_id: str,
    request: ResetGameRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    record = await run_in_threadpool(
        game_service.reset_game,
        game_id,
        request,
        _bearer_token(authorization),
    )
    response = game_service.serialize_game(record)
    await _broadcast_state(response)
    return response


@router.post("/{game_id}/invite", response_model=InviteResponse)
async def replace_invite(
    game_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> InviteResponse:
    return await run_in_threadpool(
        game_service.replace_invite,
        game_id,
        _bearer_token(authorization),
    )


@router.websocket("/ws/{game_id}")
async def game_ws(websocket: WebSocket, game_id: str) -> None:
    await websocket.accept()

    try:
        authentication = await websocket.receive_json()
        if authentication.get("type") != "authenticate":
            await socket_manager.send(
                websocket,
                "error",
                {"message": "WebSocket authentication is required", "status": 401},
            )
            await websocket.close(code=1008)
            return

        token = authentication.get("token")
        authorized = await run_in_threadpool(game_service.authorize, game_id, token)
    except HTTPException as error:
        await socket_manager.send(
            websocket,
            "error",
            {"message": str(error.detail), "status": error.status_code},
        )
        await websocket.close(code=1008)
        return
    except Exception:
        await socket_manager.send(
            websocket,
            "error",
            {"message": "WebSocket authentication payload is invalid", "status": 400},
        )
        await websocket.close(code=1008)
        return

    identity = SocketIdentity(
        color=authorized.player.color if authorized.player else None,
        role=authorized.player.role if authorized.player else "local",
    )
    await socket_manager.connect(game_id, websocket, identity, accept=False)

    try:
        await socket_manager.send(
            websocket,
            "game_state",
            {"game": game_service.serialize_game(authorized.record).model_dump(by_alias=True)},
        )
        await socket_manager.broadcast_presence(game_id)

        while True:
            message = await websocket.receive_json()
            event_type = message.get("type")
            if event_type == "ping":
                await socket_manager.send(websocket, "pong")
            elif event_type == "sync":
                latest = await run_in_threadpool(game_service.get_game, game_id, token)
                await socket_manager.send(
                    websocket,
                    "game_state",
                    {"game": game_service.serialize_game(latest).model_dump(by_alias=True)},
                )
    except WebSocketDisconnect:
        pass
    except Exception:
        # A malformed client message should only close that connection.
        await websocket.close(code=1003)
    finally:
        socket_manager.disconnect(game_id, websocket)
        await socket_manager.broadcast_presence(game_id)
