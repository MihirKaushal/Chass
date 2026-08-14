from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from fastapi import HTTPException

from backend.catalog import (
    VICTORY_MODES,
    build_catalog_piece_definitions,
    build_default_draft_pool,
    catalog_payload,
)
from backend.catalog import (
    build_default_piece_definitions as build_catalog_default_piece_definitions,
)
from backend.config import get_settings
from backend.models import (
    AbilityState,
    AffinityState,
    Board,
    BoardCoordinate,
    CenterDominionState,
    ClockState,
    CustomRulesConfig,
    GambitState,
    GameConfiguration,
    GameState,
    Move,
    MovePattern,
    Piece,
    PieceDefinition,
    RematchState,
    RuleSetting,
    SpecialAbilityConfig,
    VictoryConfig,
)
from backend.models.schemas import (
    AbilitySelectionRequest,
    AbilityStateView,
    AffinityView,
    AvailableActionView,
    BoardPlacement,
    CaptureView,
    CenterDominionView,
    ClockView,
    ConfigurationValidationResponse,
    CountdownView,
    CreateGameRequest,
    GambitConfigView,
    GambitDeploymentRequest,
    GambitDraftPlayerView,
    GambitDraftRequest,
    GambitHandoffRequest,
    GambitPowerRequest,
    GambitReadyRequest,
    GambitSetupSummaryView,
    GambitView,
    GameActionRequest,
    GameResponse,
    GameSessionResponse,
    InviteResponse,
    JoinGameRequest,
    MoveHistoryView,
    MovePatternView,
    MoveRequest,
    PieceDefinitionPatch,
    PieceDefinitionPayload,
    PieceDefinitionView,
    PieceView,
    Position,
    RematchRequest,
    RematchView,
    ResetGameRequest,
    ResultView,
    RulePatch,
    RuleView,
    SetupHandoffRequest,
    UpdateBoardLayoutRequest,
    UpdatePiecesRequest,
    UpdateRulesRequest,
    ValidMoveView,
)
from backend.repositories import (
    ConcurrentUpdateError,
    ExpiredGameError,
    GameRecord,
    GameRepository,
    InviteClaimError,
    MoveAudit,
    PlayerIdentity,
    RepositoryError,
    create_game_repository,
)
from backend.rules import RuleEngine
from backend.rules.variant_system import (
    FINISHED_STATUSES,
    ability_cooldown_remaining,
    affinity_start_squares,
    barricade_start_squares,
    public_countdowns,
)
from backend.security import (
    generate_invite_code,
    generate_token,
    hash_token,
    normalize_invite_credential,
)

DEFAULT_PIECE_POINTS: dict[str, int | None] = {
    "pawn": 1,
    "knight": 3,
    "bishop": 3,
    "rook": 5,
    "queen": 9,
    "king": None,
}


@lru_cache(maxsize=1)
def _cached_catalog() -> dict:
    return catalog_payload()


def build_default_piece_definitions() -> dict[str, PieceDefinition]:
    return build_catalog_default_piece_definitions()


def _build_back_rank(board_cols: int) -> list[str]:
    rank: list[str] = ["pawn"] * board_cols
    left = 0
    right = board_cols - 1
    cycle = ["rook", "knight", "bishop"]
    cycle_index = 0

    while right - left + 1 > 2:
        piece_type = cycle[cycle_index % len(cycle)]
        rank[left] = piece_type
        rank[right] = piece_type
        left += 1
        right -= 1
        cycle_index += 1

    if board_cols % 2 == 0:
        rank[left] = "queen"
        rank[right] = "king"
    else:
        rank[left] = "king"

    return rank


def _create_piece_instance(
    piece_type: str,
    color: str,
    piece_definitions: dict[str, PieceDefinition],
) -> Piece:
    definition = piece_definitions.get(piece_type)
    if definition is None:
        definition = PieceDefinition(
            type=piece_type,
            display_name=piece_type.title(),
            symbols={"white": "?", "black": "?"},
            points=None,
            is_custom=True,
            custom_attributes={},
            patterns=[],
            metadata={},
        )

    return Piece(
        type=piece_type,
        name=definition.display_name,
        color=color,
        points=definition.points,
        has_moved=False,
        is_custom=definition.is_custom,
        custom_attributes=dict(definition.custom_attributes),
        runtime={},
    )


def _empty_board(board_rows: int, board_cols: int) -> Board:
    grid: list[list[Piece | None]] = [[None for _ in range(board_cols)] for _ in range(board_rows)]
    return Board(rows=board_rows, cols=board_cols, grid=grid)


def _initial_board(
    board_rows: int,
    board_cols: int,
    piece_definitions: dict[str, PieceDefinition],
) -> Board:
    board = _empty_board(board_rows, board_cols)
    grid = board.grid

    if board_cols > 8:
        classic_back_rank = [
            "rook",
            "knight",
            "bishop",
            "queen",
            "king",
            "bishop",
            "knight",
            "rook",
        ]
        col_start = (board_cols - len(classic_back_rank)) // 2
        piece_columns = [col_start + index for index in range(len(classic_back_rank))]
        black_back_rank = classic_back_rank
        white_back_rank = classic_back_rank
    else:
        piece_columns = list(range(board_cols))
        black_back_rank = _build_back_rank(board_cols)
        white_back_rank = _build_back_rank(board_cols)

    if board_rows >= 1:
        for index, col in enumerate(piece_columns):
            grid[0][col] = _create_piece_instance(
                black_back_rank[index], "black", piece_definitions
            )

    if board_rows >= 2:
        for col in piece_columns:
            grid[1][col] = _create_piece_instance("pawn", "black", piece_definitions)

    if board_rows >= 2:
        for col in piece_columns:
            grid[board_rows - 2][col] = _create_piece_instance("pawn", "white", piece_definitions)

    if board_rows >= 1:
        for index, col in enumerate(piece_columns):
            grid[board_rows - 1][col] = _create_piece_instance(
                white_back_rank[index], "white", piece_definitions
            )

    return board


def _normalize_placement(
    placement: BoardPlacement,
    board_rows: int,
    board_cols: int,
    piece_definitions: dict[str, PieceDefinition],
) -> BoardPlacement:
    if placement.type not in piece_definitions:
        raise HTTPException(status_code=400, detail=f"Unknown piece type: {placement.type}")
    allowed_colors = {"white", "black"}
    if piece_definitions[placement.type].metadata.get("neutral"):
        allowed_colors.add("neutral")
    if placement.color not in allowed_colors:
        raise HTTPException(status_code=400, detail=f"Unsupported piece color: {placement.color}")
    if (
        placement.row < 0
        or placement.row >= board_rows
        or placement.col < 0
        or placement.col >= board_cols
    ):
        raise HTTPException(status_code=400, detail="Placement out of board bounds")
    return placement


def _piece_definition_from_payload(payload: PieceDefinitionPayload) -> PieceDefinition:
    symbols = {
        "white": payload.symbols.get("white", payload.symbols.get("w", "W")),
        "black": payload.symbols.get("black", payload.symbols.get("b", "B")),
    }
    return PieceDefinition(
        type=payload.type,
        display_name=payload.displayName,
        symbols=symbols,
        points=payload.points,
        is_custom=payload.isCustom,
        custom_attributes=payload.customAttributes,
        patterns=[MovePattern.model_validate(pattern.model_dump()) for pattern in payload.patterns],
        metadata=payload.metadata,
    )


def _apply_piece_patch(
    piece_definitions: dict[str, PieceDefinition],
    patch: PieceDefinitionPatch,
) -> None:
    definition = piece_definitions.get(patch.type)
    if definition is None:
        raise HTTPException(status_code=400, detail=f"Unknown piece type: {patch.type}")

    updated = definition.model_copy(deep=True)

    if "displayName" in patch.model_fields_set and patch.displayName is not None:
        updated.display_name = patch.displayName

    if "symbols" in patch.model_fields_set and patch.symbols is not None:
        updated.symbols = {
            "white": patch.symbols.get("white", patch.symbols.get("w", updated.symbols["white"])),
            "black": patch.symbols.get("black", patch.symbols.get("b", updated.symbols["black"])),
        }

    if "patterns" in patch.model_fields_set and patch.patterns is not None:
        updated.patterns = [
            MovePattern.model_validate(pattern.model_dump()) for pattern in patch.patterns
        ]

    if "points" in patch.model_fields_set:
        updated.points = patch.points

    if "isCustom" in patch.model_fields_set and patch.isCustom is not None:
        updated.is_custom = patch.isCustom

    if "customAttributes" in patch.model_fields_set and patch.customAttributes is not None:
        updated.custom_attributes = patch.customAttributes

    if "metadata" in patch.model_fields_set and patch.metadata is not None:
        updated.metadata = patch.metadata

    piece_definitions[patch.type] = updated


def _sync_piece_metadata(game_state: GameState) -> None:
    def apply_definition(piece: Piece | None) -> None:
        if piece is None:
            return
        definition = game_state.piece_definitions.get(piece.type)
        if definition is None:
            return
        piece.name = definition.display_name
        piece.points = definition.points
        piece.is_custom = definition.is_custom
        piece.custom_attributes = dict(definition.custom_attributes)

    for row in game_state.board.grid:
        for piece in row:
            apply_definition(piece)

    for color in ("white", "black"):
        for captured_piece in game_state.captured_pieces.get(color, []):
            apply_definition(captured_piece)


def _center_affinity_squares(board_rows: int, board_cols: int) -> dict[str, list[BoardCoordinate]]:
    return {
        color: [BoardCoordinate(row=row, col=col) for row, col in squares]
        for color, squares in affinity_start_squares(board_rows, board_cols).items()
    }


def _configuration_from_request(
    request: CreateGameRequest,
) -> tuple[
    GameConfiguration,
    dict[str, PieceDefinition],
    GambitState | None,
]:
    payload = request.configuration
    catalog = build_catalog_piece_definitions()
    if payload is None:
        definitions = build_default_piece_definitions()
        configuration = GameConfiguration(
            preset_id="gambit" if request.variant == "gambit" else "classic",
            custom_rules=CustomRulesConfig(
                affinity_enabled=request.variant == "gambit",
                command_point_cap=3,
            ),
        )
        gambit = GambitState() if request.variant == "gambit" else None
        if gambit is not None:
            gambit.config.require_exact_budget = False
            gambit.config.affinity_squares = _center_affinity_squares(
                request.boardRows,
                request.boardCols,
            )
        return configuration, definitions, gambit

    unknown = sorted(set(payload.enabledPieces) - set(catalog))
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown piece type: {unknown[0]}")
    if "king" not in payload.enabledPieces:
        raise HTTPException(status_code=400, detail="The King must remain enabled.")
    enabled_types = set(payload.enabledPieces)
    placement_types = {placement.type for placement in payload.initialLayout}
    disabled_placements = sorted(placement_types - enabled_types)
    if disabled_placements:
        raise HTTPException(
            status_code=400,
            detail=f"Starting piece is not enabled: {disabled_placements[0]}",
        )
    if not payload.gambit.enabled and payload.initialLayout:
        for color in ("white", "black"):
            king_count = sum(
                placement.type == "king" and placement.color == color
                for placement in payload.initialLayout
            )
            if king_count != 1:
                raise HTTPException(
                    status_code=400,
                    detail=f"{color.title()} must begin with exactly one King.",
                )

    definitions: dict[str, PieceDefinition] = {}
    for piece_type in payload.enabledPieces:
        definition = catalog[piece_type].model_copy(deep=True)
        if piece_type in payload.piecePoints:
            definition.points = payload.piecePoints[piece_type]
        if definition.points is not None and definition.points < 0:
            raise HTTPException(status_code=400, detail="Piece points cannot be negative.")
        definitions[piece_type] = definition

    custom_rules_explicit = "customRules" in payload.model_fields_set
    legacy_affinity_explicit = "affinityEnabled" in payload.gambit.model_fields_set
    affinity_enabled = payload.customRules.affinityEnabled
    command_point_cap = payload.customRules.commandPointCap
    if not custom_rules_explicit and legacy_affinity_explicit:
        affinity_enabled = bool(payload.gambit.affinityEnabled)
        command_point_cap = (
            payload.gambit.commandPointCap
            if payload.gambit.commandPointCap is not None
            else 3
        )
    elif not custom_rules_explicit and payload.gambit.enabled:
        # Older clients treated affinity as part of Gambit and omitted the field.
        affinity_enabled = True
        command_point_cap = 3

    configuration = GameConfiguration(
        schema_version=payload.schemaVersion,
        preset_id=payload.presetId,
        formation_id=payload.formationId,
        barricade_count=(payload.barricadeCount if "barricade" in enabled_types else 0),
        enabled_piece_types=list(payload.enabledPieces),
        initial_layout=[placement.model_dump() for placement in payload.initialLayout],
        victory=VictoryConfig(
            mode=payload.victory.mode,
            target_points=payload.victory.targetPoints,
            time_seconds=payload.victory.timeSeconds,
            king_points=payload.victory.kingPoints,
            dominion_rounds=payload.victory.dominionRounds,
        ),
        custom_rules=CustomRulesConfig(
            affinity_enabled=affinity_enabled,
            command_point_cap=command_point_cap,
        ),
        special_abilities=SpecialAbilityConfig(
            enabled=payload.specialAbilities.enabled,
            allowed=list(dict.fromkeys(payload.specialAbilities.allowed)),
        ),
    )

    gambit = None
    if payload.gambit.enabled:
        unknown_caps = sorted(set(payload.gambit.pieceCaps) - enabled_types)
        if unknown_caps:
            raise HTTPException(
                status_code=400,
                detail=f"Piece limit is not enabled: {unknown_caps[0]}",
            )
        unknown_draft_pool = sorted(set(payload.gambit.draftPool) - enabled_types)
        if unknown_draft_pool:
            raise HTTPException(
                status_code=400,
                detail=f"Draft pool piece is not enabled: {unknown_draft_pool[0]}",
            )
        if "barricade" in payload.gambit.draftPool:
            raise HTTPException(
                status_code=400,
                detail="Barricades are neutral and cannot enter the army draft.",
            )
        gambit = GambitState()
        gambit.config.budget = payload.gambit.budget
        gambit.config.max_pieces = payload.gambit.maxPieces
        gambit.config.setup_rows = payload.gambit.setupRows
        gambit.config.command_point_cap = configuration.custom_rules.command_point_cap
        gambit.config.affinity_enabled = configuration.custom_rules.affinity_enabled
        gambit.config.draft_enabled = payload.gambit.draftEnabled
        gambit.config.require_exact_budget = False
        gambit.config.piece_points = {
            piece_type: int(definitions[piece_type].points or 0)
            for piece_type in payload.enabledPieces
            if piece_type != "barricade"
        }
        default_caps = {
            piece_type: payload.gambit.maxPieces for piece_type in payload.enabledPieces
        }
        default_caps["king"] = 1
        default_caps["queen"] = payload.gambit.maxQueens
        default_caps["barricade"] = 0
        default_caps.update(payload.gambit.pieceCaps)
        default_caps["king"] = 1
        default_caps["queen"] = payload.gambit.maxQueens
        default_caps["barricade"] = 0
        gambit.config.piece_caps = default_caps
        draft_pool = build_default_draft_pool(enabled_types)
        draft_pool.update(payload.gambit.draftPool)
        gambit.config.draft_pool = draft_pool
        gambit.draft_pool_remaining = dict(draft_pool)
        if gambit.config.piece_points.get("king", 0) > gambit.config.budget:
            raise HTTPException(
                status_code=400,
                detail="The Gambit point limit must include the required King.",
            )
        gambit.config.affinity_squares = _center_affinity_squares(
            request.boardRows,
            request.boardCols,
        )
    # Standard promotion and command transformations remain available even when
    # their piece types are not part of the starting army catalog.
    for piece_type in ("queen", "rook", "bishop", "knight"):
        definitions.setdefault(piece_type, catalog[piece_type].model_copy(deep=True))
    return configuration, definitions, gambit


def _configured_board(
    rows: int,
    cols: int,
    definitions: dict[str, PieceDefinition],
    configuration: GameConfiguration,
) -> Board:
    def add_barricades(board: Board) -> None:
        if "barricade" not in definitions or configuration.barricade_count <= 0:
            return
        positions = barricade_start_squares(
            rows,
            cols,
            configuration.barricade_count,
        )
        for row, col in positions:
            if board.grid[row][col] is not None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Starting Barricade positions must remain empty in the center of the board."
                    ),
                )
            board.grid[row][col] = _create_piece_instance(
                "barricade",
                "neutral",
                definitions,
            )

    if not configuration.initial_layout:
        board = _initial_board(rows, cols, definitions)
        add_barricades(board)
        return board

    board = _empty_board(rows, cols)
    seen: set[tuple[int, int]] = set()
    for raw in configuration.initial_layout:
        placement = BoardPlacement.model_validate(raw)
        if placement.type == "barricade":
            # Barricades use deterministic central placement from the count setting.
            continue
        if (placement.row, placement.col) in seen:
            raise HTTPException(status_code=400, detail="Only one piece may occupy each square.")
        seen.add((placement.row, placement.col))
        normalized = _normalize_placement(placement, rows, cols, definitions)
        board.grid[normalized.row][normalized.col] = _create_piece_instance(
            normalized.type,
            normalized.color,
            definitions,
        )
    add_barricades(board)
    return board


def _apply_rule_patches(
    settings: list[RuleSetting],
    patches: list[RulePatch],
    engine: RuleEngine,
) -> list[RuleSetting]:
    settings_map = {setting.id: setting.model_copy(deep=True) for setting in settings}

    for patch in patches:
        if not engine.rule_exists(patch.id):
            raise HTTPException(status_code=400, detail=f"Unknown rule id: {patch.id}")

        current = settings_map.get(patch.id, RuleSetting(id=patch.id, enabled=True, params={}))
        rule = next(rule for rule in engine.available_rules() if rule.id == patch.id)

        if patch.enabled is not None and rule.can_disable:
            current.enabled = patch.enabled
        if patch.params is not None:
            current.params = patch.params

        settings_map[patch.id] = current

    ordered = []
    for rule in engine.available_rules():
        ordered.append(settings_map.get(rule.id, RuleSetting(id=rule.id, enabled=True, params={})))
    return ordered


@dataclass(frozen=True)
class AuthorizedGame:
    record: GameRecord
    player: PlayerIdentity | None


class GameService:
    def __init__(self, engine: RuleEngine, repository: GameRepository | None = None) -> None:
        self.engine = engine
        self.repository = repository or create_game_repository()

    @staticmethod
    def _expiration_deadline(now: datetime | None = None) -> datetime:
        current = now or datetime.now(timezone.utc)
        return current + timedelta(hours=get_settings().game_idle_ttl_hours)

    @staticmethod
    def _inactive_before(now: datetime | None = None) -> datetime:
        current = now or datetime.now(timezone.utc)
        return current - timedelta(hours=get_settings().game_idle_ttl_hours)

    def cleanup_inactive_games(self, now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        return self.repository.delete_inactive_games(
            self._inactive_before(current),
            current,
        )

    def _load_game(self, game_id: str) -> GameRecord:
        now = datetime.now(timezone.utc)
        inactive_before = self._inactive_before(now)
        try:
            record = self.repository.get_game(game_id)
        except ExpiredGameError as error:
            self.repository.delete_game_if_inactive(game_id, inactive_before, now)
            raise HTTPException(status_code=410, detail=str(error)) from error

        if record is None:
            raise HTTPException(status_code=404, detail="Game not found")

        expired = record.expires_at is not None and record.expires_at <= now
        if expired or record.updated_at <= inactive_before:
            deleted = self.repository.delete_game_if_inactive(
                game_id,
                inactive_before,
                now,
            )
            if deleted:
                raise HTTPException(
                    status_code=410,
                    detail=(
                        "Game expired after "
                        f"{get_settings().game_idle_ttl_hours} hours without activity"
                    ),
                )

            record = self.repository.get_game(game_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Game not found")

        _sync_piece_metadata(record.state)
        was_finished = record.state.phase == "finished"
        self.engine.evaluate_state(record.state)
        clock_expired = (
            not was_finished
            and record.state.phase == "finished"
            and record.state.result is not None
            and record.state.result.reason_code == "time_expired"
        )
        if clock_expired:
            try:
                record = self.repository.save_game(
                    record.state,
                    record.version,
                    expires_at=record.expires_at,
                )
            except ConcurrentUpdateError as error:
                latest = self.repository.get_game(game_id)
                if latest is None:
                    raise HTTPException(status_code=404, detail="Game not found") from error
                _sync_piece_metadata(latest.state)
                self.engine.evaluate_state(latest.state)
                record = latest
        return record

    def authorize(
        self,
        game_id: str,
        player_token: str | None,
        *,
        require_host: bool = False,
    ) -> AuthorizedGame:
        record = self._load_game(game_id)
        if record.mode == "local":
            return AuthorizedGame(record=record, player=None)

        if not player_token:
            raise HTTPException(
                status_code=401,
                detail="A player token is required for this online game",
                headers={"WWW-Authenticate": "Bearer"},
            )

        player = self.repository.get_player(game_id, hash_token(player_token))
        if player is None:
            raise HTTPException(status_code=403, detail="Player token is invalid for this game")
        if require_host and player.role != "host":
            raise HTTPException(status_code=403, detail="Only the game host can change this game")

        return AuthorizedGame(record=record, player=player)

    @staticmethod
    def _expected_version(record: GameRecord, requested: int | None) -> int:
        if requested is not None and requested != record.version:
            raise HTTPException(
                status_code=409,
                detail="Your game view is out of date. The latest position has been loaded.",
            )
        if record.mode == "online" and requested is None:
            raise HTTPException(
                status_code=428,
                detail="Online game updates must include expectedVersion",
            )
        return requested if requested is not None else record.version

    def _save(
        self,
        state: GameState,
        expected_version: int,
        audit: MoveAudit | None = None,
        *,
        preserve_rematch: bool = False,
    ) -> GameRecord:
        if not preserve_rematch and state.rematch.status == "pending":
            state.rematch = RematchState()
        try:
            return self.repository.save_game(
                state,
                expected_version,
                audit,
                expires_at=self._expiration_deadline(),
            )
        except ConcurrentUpdateError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @staticmethod
    def _invite_url(invite_token: str) -> str:
        return f"{get_settings().frontend_url}/join/{invite_token}"

    def create_game(self, request: CreateGameRequest) -> GameSessionResponse:
        validation = self.engine.configuration.validate(request)
        if not validation.valid:
            raise HTTPException(status_code=400, detail=validation.errors[0])
        configuration, piece_definitions, gambit_state = _configuration_from_request(request)
        for custom_piece in request.customPieces:
            definition = _piece_definition_from_payload(custom_piece)
            if definition.points is not None and definition.points < 0:
                raise HTTPException(status_code=400, detail="Piece points cannot be negative.")
            piece_definitions[definition.type] = definition

        rule_settings = _apply_rule_patches(
            settings=self.engine.default_rule_settings(),
            patches=request.rules,
            engine=self.engine,
        )

        is_gambit = gambit_state is not None or request.variant == "gambit"
        request.variant = "gambit" if is_gambit else "classic"
        if is_gambit and gambit_state is None:
            gambit_state = GambitState()
            gambit_state.config.affinity_squares = _center_affinity_squares(
                request.boardRows,
                request.boardCols,
            )
        if gambit_state is not None:
            try:
                gambit_state = self.engine.gambit.initialize_preparation(gambit_state)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
        abilities_enabled = configuration.special_abilities.enabled
        gambit_preparation_phase = (
            self.engine.gambit.preparation_phase(gambit_state)
            if gambit_state is not None
            else "play"
        )
        initial_phase = (
            "lobby"
            if request.mode == "online"
            and (is_gambit or abilities_enabled or configuration.victory.mode == "timed")
            else ("ability_selection" if abilities_enabled else gambit_preparation_phase)
        )
        if configuration.victory.mode in {"point_race", "king_capture", "royal_score"}:
            piece_definitions["king"].points = configuration.victory.king_points

        game_state = GameState(
            id=str(uuid.uuid4()),
            board=(
                _empty_board(request.boardRows, request.boardCols)
                if is_gambit
                else _configured_board(
                    request.boardRows,
                    request.boardCols,
                    piece_definitions,
                    configuration,
                )
            ),
            variant=request.variant,
            phase=initial_phase,
            gambit=gambit_state,
            current_player="white",
            rules=rule_settings,
            piece_definitions=piece_definitions,
            configuration=configuration,
            abilities=AbilityState(),
            clock=(
                ClockState(
                    initial_seconds=configuration.victory.time_seconds,
                    remaining_seconds={
                        "white": float(configuration.victory.time_seconds),
                        "black": float(configuration.victory.time_seconds),
                    },
                    active_color="white",
                    turn_started_at=datetime.now(timezone.utc),
                )
                if configuration.victory.mode == "timed"
                else None
            ),
            history=[],
            captured_pieces={"white": [], "black": []},
            winner=None,
            game_status="active",
            score={"white": 0, "black": 0},
        )

        self.engine.evaluate_state(game_state)

        settings = get_settings()
        now = datetime.now(timezone.utc)
        game_expires_at = self._expiration_deadline(now)

        if request.mode == "local":
            record = self.repository.create_game(
                game_state,
                mode="local",
                expires_at=game_expires_at,
            )
            return GameSessionResponse(
                game=self.serialize_game(record),
                role="local",
            )

        host_token = generate_token()
        invite_token = generate_invite_code()
        invite_expires_at = now + timedelta(hours=settings.invite_ttl_hours)
        record = self.repository.create_game(
            game_state,
            mode="online",
            expires_at=game_expires_at,
            host_token_hash=hash_token(host_token),
            invite_token_hash=hash_token(invite_token),
            invite_expires_at=invite_expires_at,
        )
        return GameSessionResponse(
            game=self.serialize_game(record, viewer_color="white"),
            playerToken=host_token,
            playerColor="white",
            role="host",
            inviteToken=invite_token,
            inviteCode=invite_token,
            inviteUrl=self._invite_url(invite_token),
            inviteExpiresAt=invite_expires_at,
        )

    def join_game(self, request: JoinGameRequest) -> GameSessionResponse:
        player_token = generate_token()
        now = datetime.now(timezone.utc)
        invite_credential = normalize_invite_credential(
            request.inviteCode or request.inviteToken or ""
        )
        try:
            record = self.repository.claim_invite(
                hash_token(invite_credential),
                hash_token(player_token),
                self._expiration_deadline(now),
                self._inactive_before(now),
            )
        except InviteClaimError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        if record.state.phase == "lobby":
            next_state = record.state.clone()
            next_state.phase = (
                "ability_selection"
                if next_state.configuration.special_abilities.enabled
                else (
                    self.engine.gambit.preparation_phase(next_state.gambit)
                    if next_state.gambit is not None
                    else "play"
                )
            )
            if next_state.gambit is not None:
                next_version = record.version + 1
                next_state.gambit.deployment_versions = {
                    "white": next_version,
                    "black": next_version,
                }
            if next_state.phase == "play" and next_state.clock is not None:
                next_state.clock.active_color = "white"
                next_state.clock.turn_started_at = now
            if next_state.phase == "play":
                self.engine.evaluate_state(next_state)
            record = self._save(next_state, record.version)

        return GameSessionResponse(
            game=self.serialize_game(record, viewer_color="black"),
            playerToken=player_token,
            playerColor="black",
            role="player",
        )

    def get_game(self, game_id: str, player_token: str | None = None) -> GameRecord:
        return self.authorize(game_id, player_token).record

    @staticmethod
    def catalog() -> dict:
        return deepcopy(_cached_catalog())

    def validate_configuration(
        self,
        request: CreateGameRequest,
    ) -> ConfigurationValidationResponse:
        return ConfigurationValidationResponse(
            **self.engine.configuration.validate(request).as_dict()
        )

    def viewer_color(self, record: GameRecord, player_token: str | None) -> str | None:
        if record.mode == "local":
            return None
        if not player_token:
            raise HTTPException(status_code=401, detail="A player token is required.")
        player = self.repository.get_player(record.state.id, hash_token(player_token))
        if player is None:
            raise HTTPException(status_code=403, detail="Player token is invalid for this game.")
        return player.color

    def replace_invite(self, game_id: str, player_token: str | None) -> InviteResponse:
        authorized = self.authorize(game_id, player_token, require_host=True)
        if authorized.record.ready:
            raise HTTPException(status_code=409, detail="This game already has two players")

        invite_token = generate_invite_code()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=get_settings().invite_ttl_hours)
        try:
            self.repository.replace_invite(
                game_id,
                hash_token(invite_token),
                expires_at,
                self._expiration_deadline(now),
            )
        except (ExpiredGameError, RepositoryError) as error:
            raise HTTPException(status_code=410, detail=str(error)) from error
        return InviteResponse(
            inviteToken=invite_token,
            inviteCode=invite_token,
            inviteUrl=self._invite_url(invite_token),
            inviteExpiresAt=expires_at,
        )

    @staticmethod
    def _setup_color(authorized: AuthorizedGame) -> str:
        state = authorized.record.state
        if authorized.record.mode == "online":
            if authorized.player is None:
                raise HTTPException(status_code=403, detail="A player seat is required.")
            return authorized.player.color
        return state.abilities.active_selection_color

    def select_ability(
        self,
        game_id: str,
        request: AbilitySelectionRequest,
        player_token: str | None = None,
    ) -> GameRecord:
        authorized = self.authorize(game_id, player_token)
        record = authorized.record
        state = record.state
        config = state.configuration.special_abilities
        if not config.enabled or state.phase != "ability_selection":
            raise HTTPException(status_code=409, detail="Ability selection is not active.")
        if request.abilityId not in config.allowed:
            raise HTTPException(
                status_code=400, detail="That ability is not enabled for this game."
            )
        if record.mode == "online" and not record.ready:
            raise HTTPException(status_code=409, detail="Waiting for the second player to join.")

        color = self._setup_color(authorized)
        if state.abilities.selected[color] is not None:
            raise HTTPException(status_code=409, detail="This ability choice is already locked.")
        expected = self._expected_version(record, request.expectedVersion)
        next_state = state.clone()
        next_state.abilities.selected[color] = request.abilityId

        if record.mode == "local" and color == "white":
            next_state.abilities.active_selection_color = "black"
            next_state.phase = "handoff"
        elif all(next_state.abilities.selected.values()):
            next_state.phase = (
                self.engine.gambit.preparation_phase(next_state.gambit)
                if next_state.gambit is not None
                else "play"
            )
            if next_state.variant == "gambit" and next_state.gambit is not None:
                next_state.gambit.active_deployment_color = "white"
            if next_state.clock is not None:
                next_state.clock.turn_started_at = datetime.now(timezone.utc)
            if next_state.phase == "play":
                self.engine.evaluate_state(next_state)
        return self._save(next_state, expected)

    def complete_setup_handoff(
        self,
        game_id: str,
        request: SetupHandoffRequest,
        player_token: str | None = None,
    ) -> GameRecord:
        authorized = self.authorize(game_id, player_token)
        record = authorized.record
        if record.mode != "local" or record.state.phase != "handoff":
            raise HTTPException(status_code=409, detail="No private handoff is waiting.")
        expected = self._expected_version(record, request.expectedVersion)
        next_state = record.state.clone()
        if (
            next_state.configuration.special_abilities.enabled
            and next_state.abilities.selected["black"] is None
        ):
            next_state.phase = "ability_selection"
        elif next_state.variant == "gambit":
            next_state.phase = self.engine.gambit.preparation_phase(next_state.gambit)
        else:
            next_state.phase = "play"
        if next_state.phase == "play":
            self.engine.evaluate_state(next_state)
        return self._save(next_state, expected)

    def use_custom_action(
        self,
        game_id: str,
        request: GameActionRequest,
        player_token: str | None = None,
    ) -> tuple[GameRecord, str]:
        authorized = self.authorize(game_id, player_token)
        record = authorized.record
        color = record.state.current_player
        if record.mode == "online":
            if not record.ready:
                raise HTTPException(
                    status_code=409, detail="Waiting for the second player to join."
                )
            if authorized.player is None or authorized.player.color != color:
                raise HTTPException(status_code=403, detail=f"Only {color} can act right now.")
        expected = self._expected_version(record, request.expectedVersion)
        try:
            next_state, explanation = self.engine.apply_custom_action(
                record.state,
                color,
                request.model_dump(exclude={"expectedVersion"}),
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        action = next_state.history[-1]
        saved = self._save(
            next_state,
            expected,
            MoveAudit(
                move_number=action.move_number,
                player_color=action.player,
                piece_type=action.piece,
                from_row=action.from_row,
                from_col=action.from_col,
                to_row=action.to_row,
                to_col=action.to_col,
                explanation=action.explanation,
            ),
        )
        return saved, explanation

    @staticmethod
    def _deployment_color(authorized: AuthorizedGame) -> str:
        state = authorized.record.state
        if state.gambit is None:
            raise HTTPException(status_code=409, detail="This is not a Chass Gambit game.")
        if authorized.record.mode == "online":
            if authorized.player is None:
                raise HTTPException(status_code=403, detail="A player seat is required.")
            return authorized.player.color
        return state.gambit.active_deployment_color

    def update_gambit_draft(
        self,
        game_id: str,
        request: GambitDraftRequest,
        player_token: str | None = None,
    ) -> GameRecord:
        authorized = self.authorize(game_id, player_token)
        record = authorized.record
        state = record.state
        if state.gambit is None or not state.gambit.config.draft_enabled:
            raise HTTPException(status_code=409, detail="This game has no shared draft.")
        if record.mode == "online":
            if not record.ready:
                raise HTTPException(
                    status_code=409, detail="Waiting for the second player to join."
                )
            if authorized.player is None:
                raise HTTPException(status_code=403, detail="A player seat is required.")
            color = authorized.player.color
            if color != state.gambit.draft_active_color:
                raise HTTPException(
                    status_code=403,
                    detail=f"It is {state.gambit.draft_active_color.title()}'s draft pick.",
                )
        else:
            color = state.gambit.draft_active_color

        expected_version = self._expected_version(record, request.expectedVersion)
        try:
            next_state = self.engine.gambit.shared_draft.apply(
                state,
                color,
                action=request.action,
                piece_type=request.pieceType,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return self._save(next_state, expected_version)

    def update_gambit_deployment(
        self,
        game_id: str,
        request: GambitDeploymentRequest,
        player_token: str | None = None,
    ) -> GameRecord:
        for attempt in range(3):
            authorized = self.authorize(game_id, player_token)
            record = authorized.record
            color = self._deployment_color(authorized)

            try:
                next_state = self.engine.gambit.update_deployment(
                    record.state,
                    color,
                    mode=record.mode,
                    room_ready=record.ready,
                    action=request.action,
                    row=request.row,
                    col=request.col,
                    piece_type=request.pieceType,
                )
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error

            try:
                return self._save(next_state, record.version)
            except HTTPException as error:
                if error.status_code != 409 or record.mode != "online" or attempt == 2:
                    raise
        raise HTTPException(status_code=409, detail="Deployment changed; please try again.")

    def ready_gambit_deployment(
        self,
        game_id: str,
        request: GambitReadyRequest,
        player_token: str | None = None,
    ) -> GameRecord:
        for attempt in range(3):
            authorized = self.authorize(game_id, player_token)
            record = authorized.record
            if record.mode == "online" and not record.ready:
                raise HTTPException(
                    status_code=409,
                    detail="Waiting for the second player to join.",
                )
            color = self._deployment_color(authorized)
            try:
                next_state = self.engine.gambit.mark_ready(
                    record.state,
                    color,
                    mode=record.mode,
                    helper=self.engine,
                )
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error

            self.engine.evaluate_state(next_state)
            try:
                return self._save(next_state, record.version)
            except HTTPException as error:
                if error.status_code != 409 or record.mode != "online" or attempt == 2:
                    raise
        raise HTTPException(status_code=409, detail="Deployment changed; please try again.")

    def complete_gambit_handoff(
        self,
        game_id: str,
        request: GambitHandoffRequest,
        player_token: str | None = None,
    ) -> GameRecord:
        authorized = self.authorize(game_id, player_token)
        record = authorized.record
        expected_version = self._expected_version(record, request.expectedVersion)
        try:
            next_state = self.engine.gambit.complete_handoff(
                record.state,
                mode=record.mode,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return self._save(next_state, expected_version)

    def use_command_power(
        self,
        game_id: str,
        request: GambitPowerRequest,
        player_token: str | None = None,
    ) -> tuple[GameRecord, str]:
        authorized = self.authorize(game_id, player_token)
        record = authorized.record
        if not record.state.configuration.custom_rules.affinity_enabled:
            raise HTTPException(
                status_code=409,
                detail="Affinity Squares are not enabled for this game.",
            )
        if record.mode == "online":
            if authorized.player is None or authorized.player.color != record.state.current_player:
                raise HTTPException(
                    status_code=403,
                    detail=f"Only {record.state.current_player} can act right now.",
                )
            color = authorized.player.color
        else:
            color = record.state.current_player

        expected_version = self._expected_version(record, request.expectedVersion)
        try:
            next_state, explanation = self.engine.apply_command_power(
                record.state,
                color,
                power=request.power,
                row=request.row,
                col=request.col,
                evolve_to=request.evolveTo,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        action_record = next_state.history[-1]
        saved = self._save(
            next_state,
            expected_version,
            MoveAudit(
                move_number=action_record.move_number,
                player_color=action_record.player,
                piece_type=action_record.piece,
                from_row=action_record.from_row,
                from_col=action_record.from_col,
                to_row=action_record.to_row,
                to_col=action_record.to_col,
                explanation=action_record.explanation,
            ),
        )
        return saved, explanation

    def use_gambit_power(
        self,
        game_id: str,
        request: GambitPowerRequest,
        player_token: str | None = None,
    ) -> tuple[GameRecord, str]:
        """Compatibility alias for the original Gambit-only endpoint."""
        return self.use_command_power(game_id, request, player_token)

    def move_piece(
        self,
        game_id: str,
        request: MoveRequest,
        player_token: str | None = None,
    ) -> tuple[GameRecord, str]:
        authorized = self.authorize(game_id, player_token)
        record = authorized.record
        game_state = record.state

        if game_state.phase != "play":
            raise HTTPException(
                status_code=409,
                detail="Setup must be complete before pieces can move.",
            )

        if record.mode == "online":
            if not record.ready:
                raise HTTPException(status_code=409, detail="Waiting for the second player to join")
            if authorized.player is None or authorized.player.color != game_state.current_player:
                raise HTTPException(
                    status_code=403,
                    detail=f"Only {game_state.current_player} can move right now",
                )

        expected_version = self._expected_version(record, request.expectedVersion)
        move = Move(
            fromRow=request.fromRow,
            fromCol=request.fromCol,
            toRow=request.toRow,
            toCol=request.toCol,
            promotion=request.promotion,
        )

        try:
            next_state, explanation = self.engine.apply_move(game_state, move)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        move_record = next_state.history[-1]
        saved = self._save(
            next_state,
            expected_version,
            MoveAudit(
                move_number=move_record.move_number,
                player_color=move_record.player,
                piece_type=move_record.piece,
                from_row=move_record.from_row,
                from_col=move_record.from_col,
                to_row=move_record.to_row,
                to_col=move_record.to_col,
                explanation=move_record.explanation,
            ),
        )
        return saved, explanation

    def update_rules(
        self,
        game_id: str,
        request: UpdateRulesRequest,
        player_token: str | None = None,
    ) -> GameRecord:
        authorized = self.authorize(game_id, player_token, require_host=True)
        record = authorized.record
        game_state = record.state
        if game_state.variant == "gambit":
            raise HTTPException(
                status_code=409,
                detail="Chass Gambit rules are managed by its dedicated variant setup.",
            )
        expected_version = self._expected_version(record, request.expectedVersion)
        game_state.rules = _apply_rule_patches(game_state.rules, request.rules, self.engine)
        self.engine.evaluate_state(game_state)
        return self._save(game_state, expected_version)

    def update_pieces(
        self,
        game_id: str,
        request: UpdatePiecesRequest,
        player_token: str | None = None,
    ) -> GameRecord:
        authorized = self.authorize(game_id, player_token, require_host=True)
        record = authorized.record
        game_state = record.state
        if game_state.variant == "gambit":
            raise HTTPException(
                status_code=409,
                detail="Piece editing is not available during a Chass Gambit match.",
            )
        expected_version = self._expected_version(record, request.expectedVersion)

        for patch in request.pieces:
            _apply_piece_patch(game_state.piece_definitions, patch)

        _sync_piece_metadata(game_state)
        self.engine.evaluate_state(game_state)
        return self._save(game_state, expected_version)

    def _reset_state(self, record: GameRecord, request: ResetGameRequest) -> GameState:
        game_state = record.state

        if game_state.variant == "gambit":
            config = (
                game_state.gambit.config.model_copy(deep=True)
                if game_state.gambit is not None
                else None
            )
            reset_gambit = GambitState(config=config) if config is not None else GambitState()
            reset_gambit = self.engine.gambit.initialize_preparation(reset_gambit)
            game_state.board = _empty_board(game_state.board.rows, game_state.board.cols)
            game_state.phase = (
                "lobby"
                if record.mode == "online" and not record.ready
                else (
                    "ability_selection"
                    if game_state.configuration.special_abilities.enabled
                    else self.engine.gambit.preparation_phase(reset_gambit)
                )
            )
            game_state.gambit = reset_gambit
            game_state.gambit.deployment_versions = {
                "white": record.version + 1,
                "black": record.version + 1,
            }
            game_state.current_player = "white"
            game_state.abilities = AbilityState()
            game_state.center_dominion = CenterDominionState()
            game_state.affinity = AffinityState()
            game_state.turn_counts = {"white": 0, "black": 0}
            game_state.history = []
            game_state.captured_pieces = {"white": [], "black": []}
            game_state.winner = None
            game_state.game_status = "active"
            game_state.score = {"white": 0, "black": 0}
            game_state.spent_score = {"white": 0, "black": 0}
            game_state.rematch = RematchState()
            game_state.result = None
            if game_state.clock is not None:
                seconds = game_state.clock.initial_seconds
                game_state.clock.remaining_seconds = {
                    "white": float(seconds),
                    "black": float(seconds),
                }
                game_state.clock.active_color = "white"
                game_state.clock.turn_started_at = datetime.now(timezone.utc)
            return game_state

        board_rows = request.boardRows if request.boardRows is not None else game_state.board.rows
        board_cols = request.boardCols if request.boardCols is not None else game_state.board.cols

        game_state.board = _configured_board(
            board_rows,
            board_cols,
            game_state.piece_definitions,
            game_state.configuration,
        )
        game_state.current_player = "white"
        game_state.phase = (
            "ability_selection" if game_state.configuration.special_abilities.enabled else "play"
        )
        game_state.abilities = AbilityState()
        game_state.center_dominion = CenterDominionState()
        game_state.affinity = AffinityState()
        game_state.turn_counts = {"white": 0, "black": 0}
        game_state.history = []
        game_state.captured_pieces = {"white": [], "black": []}
        game_state.winner = None
        game_state.game_status = "active"
        game_state.score = {"white": 0, "black": 0}
        game_state.spent_score = {"white": 0, "black": 0}
        game_state.rematch = RematchState()
        game_state.result = None
        if game_state.clock is not None:
            seconds = game_state.clock.initial_seconds
            game_state.clock.remaining_seconds = {
                "white": float(seconds),
                "black": float(seconds),
            }
            game_state.clock.active_color = "white"
            game_state.clock.turn_started_at = datetime.now(timezone.utc)

        self.engine.evaluate_state(game_state)
        return game_state

    def reset_game(
        self,
        game_id: str,
        request: ResetGameRequest,
        player_token: str | None = None,
    ) -> GameRecord:
        self.authorize(game_id, player_token)
        raise HTTPException(
            status_code=409,
            detail="A restart now requires approval from both players.",
        )

    def rematch_game(
        self,
        game_id: str,
        request: RematchRequest,
        player_token: str | None = None,
    ) -> GameRecord:
        authorized = self.authorize(game_id, player_token)
        record = authorized.record
        if not record.ready:
            raise HTTPException(
                status_code=409,
                detail="Both players must join before requesting a restart.",
            )
        expected_version = self._expected_version(record, request.expectedVersion)
        if record.mode == "online":
            if authorized.player is None:
                raise HTTPException(status_code=403, detail="A player seat is required.")
            actor = authorized.player.color
        else:
            actor = request.color
            if actor not in {"white", "black"}:
                raise HTTPException(
                    status_code=400,
                    detail="Choose White or Black for same-device approval.",
                )

        state = record.state.clone()
        proposal = state.rematch
        if request.action == "request":
            if proposal.status == "pending":
                raise HTTPException(status_code=409, detail="A restart request is already pending.")
            proposal.status = "pending"
            proposal.requested_by = actor
            proposal.approvals = {"white": False, "black": False}
            proposal.approvals[actor] = True
        elif request.action == "accept":
            if proposal.status != "pending":
                raise HTTPException(
                    status_code=409, detail="There is no restart request to accept."
                )
            proposal.approvals[actor] = True
        elif request.action == "decline":
            if proposal.status != "pending":
                raise HTTPException(
                    status_code=409, detail="There is no restart request to decline."
                )
            state.rematch = RematchState()
        elif request.action == "cancel":
            if proposal.status != "pending" or proposal.requested_by != actor:
                raise HTTPException(
                    status_code=403,
                    detail="Only the requesting player can cancel this restart request.",
                )
            state.rematch = RematchState()

        if state.rematch.status == "pending" and all(state.rematch.approvals.values()):
            state = self._reset_state(replace(record, state=state), ResetGameRequest())
        return self._save(state, expected_version, preserve_rematch=True)

    def update_board_layout(
        self,
        game_id: str,
        request: UpdateBoardLayoutRequest,
        player_token: str | None = None,
    ) -> GameRecord:
        authorized = self.authorize(game_id, player_token, require_host=True)
        record = authorized.record
        game_state = record.state
        if game_state.variant == "gambit":
            raise HTTPException(
                status_code=409,
                detail="The Gambit deployment board is edited through the War Chest.",
            )
        expected_version = self._expected_version(record, request.expectedVersion)

        board_rows = request.boardRows if request.boardRows is not None else game_state.board.rows
        board_cols = request.boardCols if request.boardCols is not None else game_state.board.cols

        board = _empty_board(board_rows, board_cols)

        for placement in request.placements:
            normalized = _normalize_placement(
                placement,
                board_rows,
                board_cols,
                game_state.piece_definitions,
            )
            board.grid[normalized.row][normalized.col] = _create_piece_instance(
                normalized.type,
                normalized.color,
                game_state.piece_definitions,
            )

        game_state.board = board
        game_state.current_player = "white"
        game_state.history = []
        game_state.captured_pieces = {"white": [], "black": []}
        game_state.winner = None
        game_state.game_status = "active"
        game_state.score = {"white": 0, "black": 0}
        game_state.center_dominion = CenterDominionState()
        game_state.affinity = AffinityState()
        game_state.result = None

        self.engine.evaluate_state(game_state)
        return self._save(game_state, expected_version)

    def serialize_game(
        self,
        record: GameRecord,
        last_explanation: str | None = None,
        viewer_color: str | None = None,
    ) -> GameResponse:
        game_state = record.state

        configuration_view = {
            "schemaVersion": game_state.configuration.schema_version,
            "presetId": game_state.configuration.preset_id,
            "formationId": game_state.configuration.formation_id,
            "barricadeCount": game_state.configuration.barricade_count,
            "enabledPieces": game_state.configuration.enabled_piece_types,
            "initialLayout": game_state.configuration.initial_layout,
            "victory": {
                "mode": game_state.configuration.victory.mode,
                "targetPoints": game_state.configuration.victory.target_points,
                "timeSeconds": game_state.configuration.victory.time_seconds,
                "kingPoints": game_state.configuration.victory.king_points,
                "dominionRounds": game_state.configuration.victory.dominion_rounds,
            },
            "customRules": {
                "affinityEnabled": (
                    game_state.configuration.custom_rules.affinity_enabled
                ),
                "commandPointCap": (
                    game_state.configuration.custom_rules.command_point_cap
                ),
            },
            "specialAbilities": {
                "enabled": game_state.configuration.special_abilities.enabled,
                "allowed": game_state.configuration.special_abilities.allowed,
            },
            "gambit": {
                "enabled": game_state.gambit is not None,
                **(
                    {
                        "budget": game_state.gambit.config.budget,
                        "maxPieces": game_state.gambit.config.max_pieces,
                        "setupRows": game_state.gambit.config.setup_rows,
                        "maxQueens": game_state.gambit.config.piece_caps.get("queen", 0),
                        "affinityEnabled": (
                            game_state.configuration.custom_rules.affinity_enabled
                        ),
                        "commandPointCap": (
                            game_state.configuration.custom_rules.command_point_cap
                        ),
                        "pieceCaps": game_state.gambit.config.piece_caps,
                        "draftEnabled": game_state.gambit.config.draft_enabled,
                        "draftPool": game_state.gambit.config.draft_pool,
                    }
                    if game_state.gambit is not None
                    else {}
                ),
            },
        }

        piece_names = {
            piece.piece_id: piece.name
            for board_row in game_state.board.grid
            for piece in board_row
            if piece is not None
        }

        def piece_view(piece: Piece) -> PieceView:
            definition = game_state.piece_definitions.get(piece.type)
            symbol = definition.symbols.get(piece.color, "?") if definition else "?"
            runtime = dict(piece.runtime)
            if piece.color in {"white", "black"}:
                current_turn = game_state.turn_counts[piece.color]
                for key in (
                    "catapult_ready_turn",
                    "pacified_until_turn",
                    "capture_immune_until_turn",
                    "love_until_turn",
                ):
                    if key in runtime:
                        runtime[f"{key}_remaining"] = max(
                            0,
                            int(runtime[key]) - current_turn,
                        )
                if (
                    piece.type == "bishop"
                    and game_state.abilities.selected.get(piece.color) == "episcopal"
                ):
                    ready_turn = int(
                        game_state.abilities.runtime[piece.color].get(
                            "episcopal_ready_turn",
                            0,
                        )
                    )
                    runtime["episcopal_ready_turn_remaining"] = max(
                        0,
                        ready_turn - current_turn,
                    )
                if piece.type == "diplomat":
                    runtime["diplomat_contacts_status"] = [
                        {
                            "targetName": piece_names.get(target_id, "enemy piece"),
                            "progress": int(progress),
                            "required": 2,
                        }
                        for target_id, progress in dict(
                            runtime.get("diplomat_contacts", {})
                        ).items()
                        if int(progress) > 0
                    ]
            return PieceView(
                pieceId=piece.piece_id,
                type=piece.type,
                name=piece.name,
                color=piece.color,
                points=piece.points,
                symbol=symbol,
                hasMoved=piece.has_moved,
                isCustom=piece.is_custom,
                icon=definition.icon if definition else "",
                description=definition.description if definition else "",
                movement=definition.movement_summary if definition else "",
                customAttributes=piece.custom_attributes,
                runtime=runtime,
            )

        board_grid = game_state.board.grid
        visible_deployment_color: str | None = None
        if game_state.variant == "gambit" and game_state.phase in {
            "lobby",
            "deployment",
            "handoff",
        }:
            visible_deployment_color, visible_pieces = self.engine.gambit.visible_deployment(
                game_state,
                viewer_color,
                mode=record.mode,
            )
            board_grid = [
                [None for _ in range(game_state.board.cols)] for _ in range(game_state.board.rows)
            ]
            if visible_deployment_color is not None:
                for placement in visible_pieces:
                    board_grid[placement.row][placement.col] = _create_piece_instance(
                        placement.type,
                        visible_deployment_color,
                        game_state.piece_definitions,
                    )
            if "barricade" in game_state.configuration.enabled_piece_types:
                for row, col in barricade_start_squares(
                    game_state.board.rows,
                    game_state.board.cols,
                    game_state.configuration.barricade_count,
                ):
                    if board_grid[row][col] is None:
                        board_grid[row][col] = _create_piece_instance(
                            "barricade",
                            "neutral",
                            game_state.piece_definitions,
                        )

        board_view: list[list[PieceView | None]] = [
            [piece_view(piece) if piece is not None else None for piece in row]
            for row in board_grid
        ]

        valid_moves = (
            self.engine.get_valid_moves_for_current_player(game_state)
            if record.ready and game_state.phase == "play"
            else []
        )

        can_view_actions = record.mode == "local" or viewer_color == game_state.current_player
        available_actions = (
            self.engine.get_available_actions(game_state, game_state.current_player)
            if record.ready and game_state.phase == "play" and can_view_actions
            else []
        )
        valid_move_views = [
            ValidMoveView(
                **{
                    "from": Position(row=move.from_row, col=move.from_col),
                    "to": Position(row=move.to_row, col=move.to_col),
                    "captures": [
                        CaptureView(
                            row=capture.row,
                            col=capture.col,
                            piece=piece_view(capture.piece),
                            reason=capture.reason,
                        )
                        for capture in move.captures
                    ],
                    "explanation": move.explanation,
                }
            )
            for move in valid_moves
        ]

        settings_map = {setting.id: setting for setting in game_state.rules}
        victory_mode_view = next(
            (mode for mode in VICTORY_MODES if mode["id"] == game_state.configuration.victory.mode),
            None,
        )
        rule_views = []
        for rule in self.engine.available_rules():
            setting = settings_map.get(rule.id, RuleSetting(id=rule.id, enabled=True, params={}))
            configured_victory = rule.id == "configured_victory"
            rule_views.append(
                RuleView(
                    id=rule.id,
                    name=(
                        victory_mode_view["name"]
                        if configured_victory and victory_mode_view
                        else rule.name
                    ),
                    description=(
                        victory_mode_view["summary"]
                        if configured_victory and victory_mode_view
                        else rule.description
                    ),
                    tier=rule.tier,
                    enabled=True if not rule.can_disable else setting.enabled,
                    canDisable=rule.can_disable,
                    isSpecial=(
                        rule.tier != "basic"
                        or (
                            configured_victory
                            and game_state.configuration.victory.mode != "checkmate"
                        )
                    ),
                    params=setting.params,
                )
            )

        if game_state.variant == "gambit":
            rule_views.extend(
                RuleView(
                    id=rule.id,
                    name=rule.name,
                    description=rule.description,
                    tier=rule.tier,
                    enabled=True,
                    canDisable=rule.can_disable,
                    isSpecial=True,
                    params={},
                )
                for rule in self.engine.gambit.available_rules(game_state)
            )

        if game_state.configuration.custom_rules.affinity_enabled:
            rule_views.extend(
                RuleView(
                    id=rule.id,
                    name=rule.name,
                    description=rule.description,
                    tier=rule.tier,
                    enabled=True,
                    canDisable=False,
                    isSpecial=True,
                    params={},
                )
                for rule in self.engine.gambit.available_command_rules()
            )

        history_views = []
        for item in game_state.history:
            history_views.append(
                MoveHistoryView(
                    moveNumber=item.move_number,
                    player=item.player,
                    piece=item.piece,
                    **{
                        "from": Position(row=item.from_row, col=item.from_col),
                        "to": Position(row=item.to_row, col=item.to_col),
                        "captures": [
                            CaptureView(
                                row=capture.row,
                                col=capture.col,
                                piece=piece_view(capture.piece),
                                reason=capture.reason,
                            )
                            for capture in item.captures
                        ],
                        "explanation": item.explanation,
                        "actionType": item.action_type,
                    },
                )
            )

        captured_pieces_view = {
            color: [piece_view(piece) for piece in pieces]
            for color, pieces in game_state.captured_pieces.items()
        }

        if last_explanation is None and game_state.history:
            last_explanation = game_state.history[-1].explanation

        affinity_config = game_state.configuration.custom_rules
        affinity_squares = affinity_start_squares(
            game_state.board.rows,
            game_state.board.cols,
        )
        command_viewer = viewer_color if record.mode == "online" else game_state.current_player
        legal_power_targets: dict[str, list[Position]] = {
            power: [] for power in affinity_config.power_costs
        }
        if (
            affinity_config.affinity_enabled
            and game_state.phase == "play"
            and command_viewer == game_state.current_player
        ):
            raw_targets = self.engine.gambit.legal_power_targets(
                game_state,
                game_state.current_player,
                self.engine,
            )
            legal_power_targets = {
                power: [Position(**target) for target in targets]
                for power, targets in raw_targets.items()
            }
        affinity_view = AffinityView(
            enabled=affinity_config.affinity_enabled,
            commandPointCap=affinity_config.command_point_cap,
            powerCosts=affinity_config.power_costs,
            powerUsageCaps=affinity_config.power_usage_caps,
            squares={
                color: [Position(row=row, col=col) for row, col in squares]
                for color, squares in affinity_squares.items()
            },
            commandPoints=game_state.affinity.command_points,
            primed=game_state.affinity.primed,
            controlled=self.engine.gambit.affinity_control(game_state),
            powerUsage=game_state.affinity.power_usage,
            legalPowerTargets=legal_power_targets,
            lastPowerExplanation=game_state.affinity.last_power_explanation,
        )

        gambit_view = None
        if game_state.variant == "gambit" and game_state.gambit is not None:
            gambit = game_state.gambit
            effective_viewer = (
                viewer_color
                if record.mode == "online"
                else (
                    visible_deployment_color
                    if game_state.phase in {"lobby", "deployment", "handoff"}
                    else (
                        gambit.draft_active_color
                        if game_state.phase == "draft"
                        else game_state.current_player
                    )
                )
            )
            setup_summary = None
            if visible_deployment_color is not None:
                summary = self.engine.gambit.setup_summary(
                    game_state,
                    visible_deployment_color,
                )
                setup_summary = GambitSetupSummaryView(**summary)

            editable_color = None
            if (
                game_state.phase == "deployment"
                and effective_viewer in {"white", "black"}
                and (record.mode == "local" or record.ready)
                and not gambit.deployment_ready[effective_viewer]
            ):
                editable_color = effective_viewer

            draft_summary = {
                color: GambitDraftPlayerView(
                    **self.engine.gambit.shared_draft.summary(game_state, color)
                )
                for color in ("white", "black")
            }
            draft_can_act = (
                game_state.phase == "draft"
                and record.ready
                and (record.mode == "local" or viewer_color == gambit.draft_active_color)
            )
            draft_options = (
                self.engine.gambit.shared_draft.options(
                    game_state,
                    gambit.draft_active_color,
                )
                if game_state.phase == "draft"
                else []
            )

            gambit_view = GambitView(
                config=GambitConfigView(
                    budget=gambit.config.budget,
                    maxPieces=gambit.config.max_pieces,
                    setupRows=gambit.config.setup_rows,
                    commandPointCap=affinity_config.command_point_cap,
                    affinityEnabled=affinity_config.affinity_enabled,
                    requireExactBudget=False,
                    draftEnabled=gambit.config.draft_enabled,
                    draftPool=gambit.config.draft_pool,
                    piecePoints=gambit.config.piece_points,
                    pieceCaps=gambit.config.piece_caps,
                    powerCosts=affinity_config.power_costs,
                    powerUsageCaps=affinity_config.power_usage_caps,
                    affinitySquares={
                        color: [Position(row=row, col=col) for row, col in squares]
                        for color, squares in affinity_squares.items()
                    },
                ),
                viewerColor=effective_viewer,
                editableColor=editable_color,
                deploymentReady=gambit.deployment_ready,
                setupSummary=setup_summary,
                setupMessage=gambit.setup_message,
                commandPoints=game_state.affinity.command_points,
                affinityPrimed=game_state.affinity.primed,
                affinityControlled=self.engine.gambit.affinity_control(game_state),
                powerUsage=game_state.affinity.power_usage,
                legalPowerTargets=legal_power_targets,
                lastPowerExplanation=game_state.affinity.last_power_explanation,
                draftActiveColor=gambit.draft_active_color,
                draftPicks=gambit.draft_picks,
                draftPoolRemaining=gambit.draft_pool_remaining,
                draftPassed=gambit.draft_passed,
                draftSummary=draft_summary,
                draftOptions=draft_options,
                draftCanAct=draft_can_act,
                draftCanPass=(
                    draft_can_act
                    and self.engine.gambit.shared_draft.can_pass(
                        game_state,
                        gambit.draft_active_color,
                    )
                ),
            )

        response_phase = game_state.phase
        if game_state.game_status in FINISHED_STATUSES:
            response_phase = "finished"

        center_dominion_view = None
        if game_state.configuration.victory.mode == "center_dominion":
            center_squares = self.engine.center_dominion.squares(game_state)
            center_dominion_view = CenterDominionView(
                targetRounds=game_state.configuration.victory.dominion_rounds,
                progress=game_state.center_dominion.progress,
                primed=game_state.center_dominion.primed,
                controlled={
                    color: self.engine.center_dominion.controls(game_state, color)
                    for color in ("white", "black")
                },
                squares={
                    color: [Position(row=row, col=col) for row, col in squares]
                    for color, squares in center_squares.items()
                },
            )

        if record.mode == "online":
            ability_viewer = viewer_color
        elif game_state.phase in {"ability_selection", "handoff"}:
            ability_viewer = game_state.abilities.active_selection_color
        elif game_state.variant == "gambit" and game_state.phase in {"draft", "deployment"}:
            ability_viewer = (
                game_state.gambit.draft_active_color
                if game_state.phase == "draft" and game_state.gambit is not None
                else visible_deployment_color
            )
        else:
            ability_viewer = game_state.current_player
        choices_revealed = game_state.phase in {"play", "finished"}
        selected_view = (
            dict(game_state.abilities.selected)
            if choices_revealed
            else {
                color: (
                    game_state.abilities.selected[color]
                    if color == ability_viewer
                    else ("locked" if game_state.abilities.selected[color] else None)
                )
                for color in ("white", "black")
            }
        )
        ability_editable_color = None
        if (
            game_state.phase == "ability_selection"
            and ability_viewer in {"white", "black"}
            and game_state.abilities.selected[ability_viewer] is None
        ):
            ability_editable_color = ability_viewer

        response_version = record.version
        if (
            game_state.variant == "gambit"
            and game_state.gambit is not None
            and record.mode == "online"
            and game_state.phase in {"lobby", "deployment", "handoff"}
            and viewer_color in {"white", "black"}
        ):
            response_version = game_state.gambit.deployment_versions[viewer_color]

        return GameResponse(
            id=game_state.id,
            mode=record.mode,
            variant=game_state.variant,
            phase=response_phase,
            version=response_version,
            ready=record.ready,
            players={
                "white": (
                    "local"
                    if record.mode == "local"
                    else ("joined" if "white" in record.player_colors else "open")
                ),
                "black": (
                    "local"
                    if record.mode == "local"
                    else ("joined" if "black" in record.player_colors else "open")
                ),
            },
            boardRows=game_state.board.rows,
            boardCols=game_state.board.cols,
            boardSize=game_state.board.size,
            board=board_view,
            currentPlayer=game_state.current_player,
            validMoves=valid_move_views,
            rules=rule_views,
            pieceDefinitions=[
                PieceDefinitionView(
                    type=definition.type,
                    displayName=definition.display_name,
                    symbols=definition.symbols,
                    points=definition.points,
                    isCustom=definition.is_custom,
                    icon=definition.icon,
                    description=definition.description,
                    movement=definition.movement_summary,
                    behavior=definition.behavior,
                    customAttributes=definition.custom_attributes,
                    metadata=definition.metadata,
                    patterns=[
                        MovePatternView(
                            dr=pattern.dr,
                            dc=pattern.dc,
                            repeat=pattern.repeat,
                            mode=pattern.mode,
                            relative_to_color=pattern.relative_to_color,
                            requires_unmoved=pattern.requires_unmoved,
                            requires_clear_path=pattern.requires_clear_path,
                        )
                        for pattern in definition.patterns
                    ],
                )
                for definition in game_state.piece_definitions.values()
            ],
            history=history_views,
            capturedPieces=captured_pieces_view,
            lastMoveExplanation=last_explanation,
            winner=game_state.winner,
            gameStatus=game_state.game_status,
            score=game_state.score,
            spentScore=game_state.spent_score,
            configuration=configuration_view,
            abilities=AbilityStateView(
                enabled=game_state.configuration.special_abilities.enabled,
                allowed=game_state.configuration.special_abilities.allowed,
                selected=selected_view,
                used=game_state.abilities.used,
                usageCount=game_state.abilities.usage_count,
                cooldowns={
                    color: {
                        ability_id: remaining
                        for ability_id in [game_state.abilities.selected.get(color)]
                        if ability_id is not None
                        and (
                            remaining := ability_cooldown_remaining(
                                game_state,
                                color,
                                ability_id,
                            )
                        )
                        > 0
                    }
                    for color in ("white", "black")
                },
                viewerSelection=(
                    game_state.abilities.selected.get(ability_viewer)
                    if ability_viewer in {"white", "black"}
                    else None
                ),
                editableColor=ability_editable_color,
            ),
            countdowns=[CountdownView(**item) for item in public_countdowns(game_state)],
            availableActions=[AvailableActionView(**item) for item in available_actions],
            result=(
                ResultView(
                    reasonCode=game_state.result.reason_code,
                    description=game_state.result.description,
                    trigger=game_state.result.trigger,
                    winner=game_state.result.winner,
                )
                if game_state.result is not None
                else None
            ),
            clock=(
                ClockView(**self.engine.clock_snapshot(game_state))
                if game_state.clock is not None
                else None
            ),
            gambit=gambit_view,
            affinity=affinity_view,
            centerDominion=center_dominion_view,
            rematch=RematchView(
                status=game_state.rematch.status,
                requestedBy=game_state.rematch.requested_by,
                approvals=game_state.rematch.approvals,
                canRespondAs=(viewer_color if viewer_color else "local"),
            ),
        )
