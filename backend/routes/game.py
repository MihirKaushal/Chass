from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from backend.models.schemas import (
    AbilitySelectionRequest,
    ConfigurationValidationResponse,
    CreateGameRequest,
    GambitDeploymentRequest,
    GambitDraftRequest,
    GambitHandoffRequest,
    GambitPowerRequest,
    GambitReadyRequest,
    GameActionRequest,
    GameResponse,
    GameSessionResponse,
    HistoryPageResponse,
    InviteResponse,
    JoinGameRequest,
    MoveRequest,
    RematchRequest,
    ResetGameRequest,
    SetupHandoffRequest,
    UpdateBoardLayoutRequest,
    UpdatePiecesRequest,
    UpdateRulesRequest,
)
from backend.rate_limit import rate_limiter
from backend.realtime import SocketIdentity, socket_manager
from backend.repositories import (
    DEFAULT_HISTORY_PAGE_SIZE,
    MAX_HISTORY_PAGE_SIZE,
    GameRecord,
)
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


async def _broadcast_state(
    record: GameRecord,
    *,
    event_type: str = "game_state",
    last_explanation: str | None = None,
    target_color: str | None = None,
) -> None:
    await socket_manager.broadcast_personalized(
        record.state.id,
        event_type,
        lambda identity: {
            "game": game_service.serialize_game(
                record,
                last_explanation=last_explanation,
                viewer_color=identity.color,
            ).model_dump(by_alias=True)
        },
        identity_filter=(
            (lambda identity: identity.color == target_color) if target_color is not None else None
        ),
    )


@router.post("/create", response_model=GameSessionResponse)
async def create_game(payload: CreateGameRequest, request: Request) -> GameSessionResponse:
    rate_limiter.check(request, "create", limit=20, window_seconds=3600)
    return await run_in_threadpool(game_service.create_game, payload)


@router.post("/validate", response_model=ConfigurationValidationResponse)
async def validate_game_configuration(
    payload: CreateGameRequest,
    request: Request,
) -> ConfigurationValidationResponse:
    rate_limiter.check(request, "validate", limit=120, window_seconds=60)
    return await run_in_threadpool(game_service.validate_configuration, payload)


@router.get("/catalog")
async def get_catalog() -> dict:
    return game_service.catalog()


@router.post("/join", response_model=GameSessionResponse)
async def join_game(payload: JoinGameRequest, request: Request) -> GameSessionResponse:
    rate_limiter.check(request, "join", limit=30, window_seconds=60)
    response = await run_in_threadpool(game_service.join_game, payload)
    authorized = await run_in_threadpool(
        game_service.authorize,
        response.game.id,
        response.playerToken,
    )
    await socket_manager.broadcast(
        response.game.id,
        "player_joined",
        {"color": response.playerColor},
    )
    await _broadcast_state(authorized.record)
    await socket_manager.broadcast_presence(response.game.id)
    return response


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(
    game_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    authorized = await run_in_threadpool(
        game_service.authorize,
        game_id,
        token,
    )
    return game_service.serialize_game(
        authorized.record,
        viewer_color=authorized.player.color if authorized.player else None,
    )


@router.get("/{game_id}/history", response_model=HistoryPageResponse)
async def get_game_history(
    game_id: str,
    request: Request,
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_HISTORY_PAGE_SIZE),
    ] = DEFAULT_HISTORY_PAGE_SIZE,
    authorization: Annotated[str | None, Header()] = None,
) -> HistoryPageResponse:
    token = _bearer_token(authorization)
    rate_limiter.check(
        request,
        "history",
        limit=120,
        window_seconds=60,
        discriminator=game_id,
    )
    return await run_in_threadpool(
        game_service.get_history_page,
        game_id,
        before,
        limit,
        token,
    )


@router.post("/{game_id}/move", response_model=GameResponse)
async def make_move(
    game_id: str,
    payload: MoveRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
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
        token,
    )
    response = game_service.serialize_game(
        record,
        last_explanation=explanation,
        viewer_color=game_service.viewer_color(record, token),
    )
    await _broadcast_state(record, last_explanation=explanation)
    if response.phase == "finished":
        await _broadcast_state(
            record,
            event_type="game_ended",
            last_explanation=explanation,
        )
    return response


@router.post("/{game_id}/action", response_model=GameResponse)
async def use_custom_action(
    game_id: str,
    payload: GameActionRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    rate_limiter.check(
        request,
        "game_action",
        limit=120,
        window_seconds=60,
        discriminator=game_id,
    )
    record, explanation = await run_in_threadpool(
        game_service.use_custom_action,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        last_explanation=explanation,
        viewer_color=game_service.viewer_color(record, token),
    )
    await _broadcast_state(record, last_explanation=explanation)
    if response.phase == "finished":
        await _broadcast_state(
            record,
            event_type="game_ended",
            last_explanation=explanation,
        )
    return response


@router.post("/{game_id}/ability", response_model=GameResponse)
async def select_ability(
    game_id: str,
    payload: AbilitySelectionRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record = await run_in_threadpool(
        game_service.select_ability,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=game_service.viewer_color(record, token),
    )
    await _broadcast_state(record)
    return response


@router.post("/{game_id}/setup/handoff", response_model=GameResponse)
async def complete_setup_handoff(
    game_id: str,
    payload: SetupHandoffRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record = await run_in_threadpool(
        game_service.complete_setup_handoff,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=game_service.viewer_color(record, token),
    )
    await _broadcast_state(record)
    return response


@router.post("/{game_id}/rules", response_model=GameResponse)
async def update_rules(
    game_id: str,
    request: UpdateRulesRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record = await run_in_threadpool(
        game_service.update_rules,
        game_id,
        request,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=game_service.viewer_color(record, token),
    )
    await _broadcast_state(record)
    return response


@router.post("/{game_id}/pieces", response_model=GameResponse)
async def update_pieces(
    game_id: str,
    request: UpdatePiecesRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record = await run_in_threadpool(
        game_service.update_pieces,
        game_id,
        request,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=game_service.viewer_color(record, token),
    )
    await _broadcast_state(record)
    return response


@router.post("/{game_id}/layout", response_model=GameResponse)
async def update_board_layout(
    game_id: str,
    request: UpdateBoardLayoutRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record = await run_in_threadpool(
        game_service.update_board_layout,
        game_id,
        request,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=game_service.viewer_color(record, token),
    )
    await _broadcast_state(record)
    return response


@router.post("/{game_id}/reset", response_model=GameResponse)
async def reset_game(
    game_id: str,
    request: ResetGameRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record = await run_in_threadpool(
        game_service.reset_game,
        game_id,
        request,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=game_service.viewer_color(record, token),
    )
    await _broadcast_state(record)
    return response


@router.post("/{game_id}/rematch", response_model=GameResponse)
async def rematch_game(
    game_id: str,
    request: RematchRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record = await run_in_threadpool(
        game_service.rematch_game,
        game_id,
        request,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=game_service.viewer_color(record, token),
    )
    await _broadcast_state(record, event_type="rematch_state")
    return response


@router.post("/{game_id}/gambit/deployment", response_model=GameResponse)
async def update_gambit_deployment(
    game_id: str,
    payload: GambitDeploymentRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    rate_limiter.check(
        request,
        "gambit_deployment",
        limit=180,
        window_seconds=60,
        discriminator=game_id,
    )
    record = await run_in_threadpool(
        game_service.update_gambit_deployment,
        game_id,
        payload,
        token,
    )
    viewer_color = game_service.viewer_color(record, token)
    response = game_service.serialize_game(
        record,
        viewer_color=viewer_color,
    )
    await _broadcast_state(
        record,
        target_color=viewer_color if record.mode == "online" else None,
    )
    return response


@router.post("/{game_id}/gambit/draft", response_model=GameResponse)
async def update_gambit_draft(
    game_id: str,
    payload: GambitDraftRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    rate_limiter.check(
        request,
        "gambit_draft",
        limit=120,
        window_seconds=60,
        discriminator=game_id,
    )
    record = await run_in_threadpool(
        game_service.update_gambit_draft,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=game_service.viewer_color(record, token),
    )
    await _broadcast_state(record)
    return response


@router.post("/{game_id}/gambit/ready", response_model=GameResponse)
async def ready_gambit_deployment(
    game_id: str,
    payload: GambitReadyRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record = await run_in_threadpool(
        game_service.ready_gambit_deployment,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=game_service.viewer_color(record, token),
    )
    await _broadcast_state(record)
    return response


@router.post("/{game_id}/gambit/handoff", response_model=GameResponse)
async def complete_gambit_handoff(
    game_id: str,
    payload: GambitHandoffRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record = await run_in_threadpool(
        game_service.complete_gambit_handoff,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=game_service.viewer_color(record, token),
    )
    await _broadcast_state(record)
    return response


@router.post("/{game_id}/command", response_model=GameResponse)
@router.post("/{game_id}/gambit/power", response_model=GameResponse)
async def use_command_power(
    game_id: str,
    payload: GambitPowerRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    rate_limiter.check(
        request,
        "command_power",
        limit=120,
        window_seconds=60,
        discriminator=game_id,
    )
    record, explanation = await run_in_threadpool(
        game_service.use_command_power,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        last_explanation=explanation,
        viewer_color=game_service.viewer_color(record, token),
    )
    await _broadcast_state(record, last_explanation=explanation)
    if response.phase == "finished":
        await _broadcast_state(
            record,
            event_type="game_ended",
            last_explanation=explanation,
        )
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
            {
                "game": game_service.serialize_game(
                    authorized.record,
                    viewer_color=identity.color,
                ).model_dump(by_alias=True)
            },
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
                    {
                        "game": game_service.serialize_game(
                            latest,
                            viewer_color=identity.color,
                        ).model_dump(by_alias=True)
                    },
                )
    except WebSocketDisconnect:
        pass
    except Exception:
        # A malformed client message should only close that connection.
        await websocket.close(code=1003)
    finally:
        socket_manager.disconnect(game_id, websocket)
        await socket_manager.broadcast_presence(game_id)
