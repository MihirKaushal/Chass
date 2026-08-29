from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Annotated

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from starlette.concurrency import run_in_threadpool

from backend.analysis import (
    ChassAnalysisProvider,
    FairyStockfishUciProvider,
    MatchAnalysisService,
    StockfishUciProvider,
)
from backend.bots import (
    BotTurnScheduler,
    ChassBotEngine,
    FairyStockfishBotEngine,
    StockfishClassicBotEngine,
    bot_action_needed,
    get_bot_profile,
    verify_bot_compatibility,
)
from backend.config import get_settings
from backend.models.schemas import (
    AbilitySelectionRequest,
    BotCompatibilityView,
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
    MatchAnalysisView,
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
logger = logging.getLogger(__name__)
rule_engine = RuleEngine()
game_service = GameService(rule_engine)
analysis_settings = get_settings()
stockfish_provider = StockfishUciProvider(
    configured_path=analysis_settings.stockfish_path,
    enabled=analysis_settings.match_predictor_engine_enabled,
    movetime_ms=analysis_settings.stockfish_movetime_ms,
    hash_mb=analysis_settings.stockfish_hash_mb,
    threads=analysis_settings.stockfish_threads,
    startup_timeout_seconds=analysis_settings.stockfish_startup_timeout_seconds,
    startup_attempts=analysis_settings.stockfish_startup_attempts,
)
fairy_stockfish_provider = FairyStockfishUciProvider(
    configured_path=analysis_settings.fairy_stockfish_path,
    enabled=analysis_settings.match_predictor_engine_enabled,
    movetime_ms=analysis_settings.fairy_stockfish_movetime_ms,
    hash_mb=analysis_settings.fairy_stockfish_hash_mb,
    threads=analysis_settings.fairy_stockfish_threads,
    startup_timeout_seconds=analysis_settings.stockfish_startup_timeout_seconds,
    startup_attempts=analysis_settings.stockfish_startup_attempts,
    max_loaded_profiles=analysis_settings.fairy_stockfish_max_profiles,
)
match_analysis_service = MatchAnalysisService(
    stockfish_provider,
    rule_engine,
    fairy_provider=fairy_stockfish_provider,
    chass_provider=ChassAnalysisProvider(
        rule_engine,
        enabled=analysis_settings.match_predictor_engine_enabled,
        movetime_ms=analysis_settings.chass_engine_movetime_ms,
    ),
)
classic_bot_engine = StockfishClassicBotEngine(stockfish_provider, rule_engine)
fairy_bot_engine = FairyStockfishBotEngine(
    fairy_stockfish_provider,
    rule_engine,
    match_analysis_service,
)
chass_bot_engine = ChassBotEngine(rule_engine)
bot_engines = {
    classic_bot_engine.engine_id: classic_bot_engine,
    fairy_bot_engine.engine_id: fairy_bot_engine,
    chass_bot_engine.engine_id: chass_bot_engine,
}


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
    serialized_views: dict[str | None, GameResponse | dict] | None = None,
) -> None:
    match_analysis_service.invalidate(record.state.id)
    views = serialized_views if serialized_views is not None else {}

    def payload_for_identity(identity: SocketIdentity) -> dict:
        if identity.color not in views:
            views[identity.color] = game_service.serialize_game(
                record,
                last_explanation=last_explanation,
                viewer_color=identity.color,
            )
        view = views[identity.color]
        if isinstance(view, GameResponse):
            view = view.model_dump(by_alias=True)
            views[identity.color] = view
        return {"game": view}

    await socket_manager.broadcast_personalized(
        record.state.id,
        event_type,
        payload_for_identity,
        identity_filter=(
            (lambda identity: identity.color == target_color) if target_color is not None else None
        ),
    )


async def _broadcast_match_analysis(analysis: MatchAnalysisView) -> None:
    await socket_manager.broadcast(
        analysis.gameId,
        "match_analysis",
        {"analysis": analysis.model_dump(mode="json")},
    )


match_analysis_service.set_listener(_broadcast_match_analysis)


def _bot_turn_needed(record: GameRecord) -> bool:
    return bool(
        record.mode == "bot"
        and bot_action_needed(record.state)
    )


async def _run_bot_turn(game_id: str, expected_version: int) -> None:
    try:
        current_version = expected_version
        for _ in range(64):
            context = await run_in_threadpool(
                game_service.bot_turn_context,
                game_id,
                current_version,
            )
            engine_id = context.state.bot.engine_id if context.state.bot is not None else ""
            bot_engine = bot_engines.get(engine_id)
            if bot_engine is None:
                raise RuntimeError(
                    f"No bot engine is registered for {engine_id or 'this game'}."
                )
            try:
                decision = await bot_engine.choose_action(context)
            except Exception:
                if engine_id == chass_bot_engine.engine_id:
                    raise
                fallback_profile_id = (
                    "chass-500"
                    if context.state.bot is not None
                    and context.state.bot.target_elo <= 500
                    else "chass-800"
                )
                logger.warning(
                    "%s bot failed for %s; continuing with %s",
                    engine_id or "External",
                    game_id,
                    fallback_profile_id,
                    exc_info=True,
                )
                decision = await chass_bot_engine.choose_action(
                    replace(context, profile_id=fallback_profile_id)
                )
            record, explanation = await run_in_threadpool(
                game_service.apply_bot_decision,
                game_id,
                decision,
                current_version,
            )
            viewer_color = record.state.bot.human_color if record.state.bot else None
            response = game_service.serialize_game(
                record,
                last_explanation=explanation,
                viewer_color=viewer_color,
            )
            serialized_views = {viewer_color: response}
            await _broadcast_state(
                record,
                last_explanation=explanation,
                serialized_views=serialized_views,
            )
            if response.phase == "finished":
                await _broadcast_state(
                    record,
                    event_type="game_ended",
                    last_explanation=explanation,
                    serialized_views=serialized_views,
                )
            if not _bot_turn_needed(record):
                if record.state.phase in {"play", "finished"}:
                    await match_analysis_service.request(record.state, record.version)
                return
            current_version = record.version
        raise RuntimeError("The bot exceeded the safe consecutive-action limit.")
    except asyncio.CancelledError:
        raise
    except HTTPException as error:
        if error.status_code != 409:
            logger.warning("Bot turn failed for %s: %s", game_id, error.detail)
            await socket_manager.broadcast(
                game_id,
                "bot_error",
                {
                    "message": "The chess bot could not move. Reload to retry.",
                    "recoverable": True,
                },
            )
    except Exception:
        logger.exception("Bot turn failed for game %s", game_id)
        await socket_manager.broadcast(
            game_id,
            "bot_error",
            {
                "message": "The chess bot is temporarily unavailable. Reload to retry.",
                "recoverable": True,
            },
        )


bot_turn_scheduler = BotTurnScheduler(_run_bot_turn)


async def _ensure_bot_turn(record: GameRecord) -> None:
    if not _bot_turn_needed(record):
        return
    if bot_turn_scheduler.is_scheduled(record.state.id):
        return
    if bot_turn_scheduler.schedule(record.state.id, record.version):
        await socket_manager.broadcast(
            record.state.id,
            "bot_thinking",
            {
                "gameVersion": record.version,
                "profileId": record.state.bot.profile_id if record.state.bot else None,
                "targetElo": record.state.bot.target_elo if record.state.bot else None,
            },
        )


@router.post("/create", response_model=GameSessionResponse)
async def create_game(payload: CreateGameRequest, request: Request) -> GameSessionResponse:
    rate_limiter.check(request, "create", limit=20, window_seconds=3600)
    if payload.mode == "bot":
        state = await run_in_threadpool(game_service.configuration_bot_state, payload)
        if state is not None:
            try:
                selected_profile = get_bot_profile(payload.bot.profileId if payload.bot else "")
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
            bot_compatibility = await verify_bot_compatibility(
                state,
                match_analysis_service,
                verify=True,
            )
            if not bot_compatibility.eligible:
                raise HTTPException(
                    status_code=503 if bot_compatibility.status == "unavailable" else 400,
                    detail=(
                        bot_compatibility.reason
                        or "This configuration cannot use a chess bot."
                    ),
                )
            if selected_profile.engine_id != bot_compatibility.engine_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Choose a {bot_compatibility.engine_name or 'compatible'} "
                        "difficulty for this configuration."
                    ),
                )
    response = await run_in_threadpool(game_service.create_game, payload)
    if response.game.mode == "bot":
        record = await run_in_threadpool(game_service.get_game, response.game.id)
        await _ensure_bot_turn(record)
    return response


@router.post("/validate", response_model=ConfigurationValidationResponse)
async def validate_game_configuration(
    payload: CreateGameRequest,
    request: Request,
) -> ConfigurationValidationResponse:
    rate_limiter.check(request, "validate", limit=120, window_seconds=60)
    validation = await run_in_threadpool(game_service.validate_configuration, payload)
    bot_state = await run_in_threadpool(game_service.configuration_bot_state, payload)
    analysis_state = await run_in_threadpool(
        game_service.configuration_analysis_state,
        payload,
    )
    bot_compatibility = await verify_bot_compatibility(
        bot_state,
        match_analysis_service,
        verify=validation.valid,
    )
    compatibility = await match_analysis_service.configuration_compatibility(
        analysis_state,
        verify=validation.valid,
    )
    return validation.model_copy(
        update={
            "matchPredictor": compatibility,
            "bot": BotCompatibilityView(**bot_compatibility.api_view()),
        }
    )


@router.get("/catalog")
async def get_catalog(response: Response) -> dict:
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=86400"
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
    await _broadcast_state(
        authorized.record,
        serialized_views={response.playerColor: response.game},
    )
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
    response = game_service.serialize_game(
        authorized.record,
        viewer_color=game_service.viewer_color(authorized.record, token),
    )
    await _ensure_bot_turn(authorized.record)
    return response


@router.get("/{game_id}/analysis", response_model=MatchAnalysisView)
async def get_match_analysis(
    game_id: str,
    request: Request,
    retry: bool = False,
    authorization: Annotated[str | None, Header()] = None,
) -> MatchAnalysisView:
    token = _bearer_token(authorization)
    rate_limiter.check(
        request,
        "match-analysis",
        limit=120,
        window_seconds=60,
        discriminator=game_id,
    )
    authorized = await run_in_threadpool(
        game_service.authorize,
        game_id,
        token,
    )
    return await match_analysis_service.request(
        authorized.record.state,
        authorized.record.version,
        retry_failed=retry,
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
    record, explanation, viewer_color = await run_in_threadpool(
        game_service.move_piece,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        last_explanation=explanation,
        viewer_color=viewer_color,
    )
    serialized_views = {viewer_color: response}
    await _broadcast_state(
        record,
        last_explanation=explanation,
        serialized_views=serialized_views,
    )
    if response.phase == "finished":
        await _broadcast_state(
            record,
            event_type="game_ended",
            last_explanation=explanation,
            serialized_views=serialized_views,
        )
    if record.mode == "bot" and response.phase != "finished":
        await _ensure_bot_turn(record)
    else:
        await match_analysis_service.request(record.state, record.version)
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
    record, explanation, viewer_color = await run_in_threadpool(
        game_service.use_custom_action,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        last_explanation=explanation,
        viewer_color=viewer_color,
    )
    serialized_views = {viewer_color: response}
    await _broadcast_state(
        record,
        last_explanation=explanation,
        serialized_views=serialized_views,
    )
    if response.phase == "finished":
        await _broadcast_state(
            record,
            event_type="game_ended",
            last_explanation=explanation,
            serialized_views=serialized_views,
        )
    if record.mode == "bot" and response.phase != "finished":
        await _ensure_bot_turn(record)
    else:
        await match_analysis_service.request(record.state, record.version)
    return response


@router.post("/{game_id}/ability", response_model=GameResponse)
async def select_ability(
    game_id: str,
    payload: AbilitySelectionRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record, viewer_color = await run_in_threadpool(
        game_service.select_ability,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=viewer_color,
    )
    await _broadcast_state(record, serialized_views={viewer_color: response})
    await _ensure_bot_turn(record)
    return response


@router.post("/{game_id}/setup/handoff", response_model=GameResponse)
async def complete_setup_handoff(
    game_id: str,
    payload: SetupHandoffRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record, viewer_color = await run_in_threadpool(
        game_service.complete_setup_handoff,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=viewer_color,
    )
    await _broadcast_state(record, serialized_views={viewer_color: response})
    return response


@router.post("/{game_id}/rules", response_model=GameResponse)
async def update_rules(
    game_id: str,
    request: UpdateRulesRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record, viewer_color = await run_in_threadpool(
        game_service.update_rules,
        game_id,
        request,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=viewer_color,
    )
    await _broadcast_state(record, serialized_views={viewer_color: response})
    return response


@router.post("/{game_id}/pieces", response_model=GameResponse)
async def update_pieces(
    game_id: str,
    request: UpdatePiecesRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record, viewer_color = await run_in_threadpool(
        game_service.update_pieces,
        game_id,
        request,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=viewer_color,
    )
    await _broadcast_state(record, serialized_views={viewer_color: response})
    return response


@router.post("/{game_id}/layout", response_model=GameResponse)
async def update_board_layout(
    game_id: str,
    request: UpdateBoardLayoutRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record, viewer_color = await run_in_threadpool(
        game_service.update_board_layout,
        game_id,
        request,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=viewer_color,
    )
    await _broadcast_state(record, serialized_views={viewer_color: response})
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
    record, viewer_color = await run_in_threadpool(
        game_service.rematch_game,
        game_id,
        request,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=viewer_color,
    )
    await _broadcast_state(
        record,
        event_type="rematch_state",
        serialized_views={viewer_color: response},
    )
    await _ensure_bot_turn(record)
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
    record, viewer_color = await run_in_threadpool(
        game_service.update_gambit_deployment,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=viewer_color,
    )
    await _broadcast_state(
        record,
        target_color=viewer_color if record.mode == "online" else None,
        serialized_views={viewer_color: response},
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
    record, viewer_color = await run_in_threadpool(
        game_service.update_gambit_draft,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=viewer_color,
    )
    await _broadcast_state(record, serialized_views={viewer_color: response})
    await _ensure_bot_turn(record)
    return response


@router.post("/{game_id}/gambit/ready", response_model=GameResponse)
async def ready_gambit_deployment(
    game_id: str,
    payload: GambitReadyRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record, viewer_color = await run_in_threadpool(
        game_service.ready_gambit_deployment,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=viewer_color,
    )
    await _broadcast_state(record, serialized_views={viewer_color: response})
    await _ensure_bot_turn(record)
    return response


@router.post("/{game_id}/gambit/handoff", response_model=GameResponse)
async def complete_gambit_handoff(
    game_id: str,
    payload: GambitHandoffRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GameResponse:
    token = _bearer_token(authorization)
    record, viewer_color = await run_in_threadpool(
        game_service.complete_gambit_handoff,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        viewer_color=viewer_color,
    )
    await _broadcast_state(record, serialized_views={viewer_color: response})
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
    record, explanation, viewer_color = await run_in_threadpool(
        game_service.use_command_power,
        game_id,
        payload,
        token,
    )
    response = game_service.serialize_game(
        record,
        last_explanation=explanation,
        viewer_color=viewer_color,
    )
    serialized_views = {viewer_color: response}
    await _broadcast_state(
        record,
        last_explanation=explanation,
        serialized_views=serialized_views,
    )
    if response.phase == "finished":
        await _broadcast_state(
            record,
            event_type="game_ended",
            last_explanation=explanation,
            serialized_views=serialized_views,
        )
    if record.mode == "bot" and response.phase != "finished":
        await _ensure_bot_turn(record)
    else:
        await match_analysis_service.request(record.state, record.version)
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


@router.post("/{game_id}/reconnect-invite", response_model=InviteResponse)
async def create_reconnect_invite(
    game_id: str,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> InviteResponse:
    rate_limiter.check(
        request,
        "reconnect-invite",
        limit=12,
        window_seconds=60,
        discriminator=game_id,
    )
    token = _bearer_token(authorization)
    target_color = await run_in_threadpool(
        game_service.reconnect_target,
        game_id,
        token,
    )
    if socket_manager.is_color_connected(game_id, target_color):
        raise HTTPException(
            status_code=409,
            detail=f"{target_color.title()} has already reconnected",
        )
    return await run_in_threadpool(
        game_service.create_reconnect_invite,
        game_id,
        token,
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
        color=(
            authorized.player.color
            if authorized.player
            else (
                authorized.record.state.bot.human_color
                if authorized.record.state.bot is not None
                else None
            )
        ),
        role=(
            authorized.player.role
            if authorized.player
            else ("human" if authorized.record.mode == "bot" else "local")
        ),
    )
    if identity.color is not None and authorized.record.mode == "online":
        try:
            await run_in_threadpool(
                game_service.revoke_reconnect_invites,
                game_id,
                identity.color,
            )
        except Exception:
            await socket_manager.send(
                websocket,
                "error",
                {
                    "message": "Unable to secure this player seat. Reconnecting...",
                    "status": 503,
                },
            )
            await websocket.close(code=1011)
            return
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
        await _ensure_bot_turn(authorized.record)
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
