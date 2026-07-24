from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from backend.config import get_settings
from backend.models import Board, GameState, Move, MovePattern, Piece, PieceDefinition, RuleSetting
from backend.models.schemas import (
    BoardPlacement,
    CaptureView,
    CreateGameRequest,
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
    ResetGameRequest,
    RulePatch,
    RuleView,
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
)
from backend.rules import RuleEngine
from backend.security import generate_token, hash_token

DEFAULT_PIECE_POINTS: dict[str, int | None] = {
    "pawn": 1,
    "knight": 3,
    "bishop": 3,
    "rook": 5,
    "queen": 9,
    "king": None,
}


def build_default_piece_definitions() -> dict[str, PieceDefinition]:
    return {
        "pawn": PieceDefinition(
            type="pawn",
            display_name="Pawn",
            symbols={"white": "\u2659", "black": "\u265F"},
            points=DEFAULT_PIECE_POINTS["pawn"],
            is_custom=False,
            custom_attributes={},
            patterns=[
                MovePattern(
                    dr=-1,
                    dc=0,
                    mode="move",
                    repeat=False,
                    relative_to_color=True,
                    requires_clear_path=True,
                ),
                MovePattern(
                    dr=-2,
                    dc=0,
                    mode="move",
                    repeat=False,
                    relative_to_color=True,
                    requires_unmoved=True,
                    requires_clear_path=True,
                ),
                MovePattern(dr=-1, dc=1, mode="capture", repeat=False, relative_to_color=True),
                MovePattern(dr=-1, dc=-1, mode="capture", repeat=False, relative_to_color=True),
            ],
            metadata={"family": "classic"},
        ),
        "rook": PieceDefinition(
            type="rook",
            display_name="Rook",
            symbols={"white": "\u2656", "black": "\u265C"},
            points=DEFAULT_PIECE_POINTS["rook"],
            is_custom=False,
            custom_attributes={},
            patterns=[
                MovePattern(dr=1, dc=0, repeat=True, mode="both", requires_clear_path=True),
                MovePattern(dr=-1, dc=0, repeat=True, mode="both", requires_clear_path=True),
                MovePattern(dr=0, dc=1, repeat=True, mode="both", requires_clear_path=True),
                MovePattern(dr=0, dc=-1, repeat=True, mode="both", requires_clear_path=True),
            ],
            metadata={"family": "classic"},
        ),
        "knight": PieceDefinition(
            type="knight",
            display_name="Knight",
            symbols={"white": "\u2658", "black": "\u265E"},
            points=DEFAULT_PIECE_POINTS["knight"],
            is_custom=False,
            custom_attributes={},
            patterns=[
                MovePattern(dr=-2, dc=-1),
                MovePattern(dr=-2, dc=1),
                MovePattern(dr=-1, dc=-2),
                MovePattern(dr=-1, dc=2),
                MovePattern(dr=1, dc=-2),
                MovePattern(dr=1, dc=2),
                MovePattern(dr=2, dc=-1),
                MovePattern(dr=2, dc=1),
            ],
            metadata={"family": "classic"},
        ),
        "bishop": PieceDefinition(
            type="bishop",
            display_name="Bishop",
            symbols={"white": "\u2657", "black": "\u265D"},
            points=DEFAULT_PIECE_POINTS["bishop"],
            is_custom=False,
            custom_attributes={},
            patterns=[
                MovePattern(dr=1, dc=1, repeat=True, requires_clear_path=True),
                MovePattern(dr=1, dc=-1, repeat=True, requires_clear_path=True),
                MovePattern(dr=-1, dc=1, repeat=True, requires_clear_path=True),
                MovePattern(dr=-1, dc=-1, repeat=True, requires_clear_path=True),
            ],
            metadata={"family": "classic"},
        ),
        "queen": PieceDefinition(
            type="queen",
            display_name="Queen",
            symbols={"white": "\u2655", "black": "\u265B"},
            points=DEFAULT_PIECE_POINTS["queen"],
            is_custom=False,
            custom_attributes={},
            patterns=[
                MovePattern(dr=1, dc=0, repeat=True, requires_clear_path=True),
                MovePattern(dr=-1, dc=0, repeat=True, requires_clear_path=True),
                MovePattern(dr=0, dc=1, repeat=True, requires_clear_path=True),
                MovePattern(dr=0, dc=-1, repeat=True, requires_clear_path=True),
                MovePattern(dr=1, dc=1, repeat=True, requires_clear_path=True),
                MovePattern(dr=1, dc=-1, repeat=True, requires_clear_path=True),
                MovePattern(dr=-1, dc=1, repeat=True, requires_clear_path=True),
                MovePattern(dr=-1, dc=-1, repeat=True, requires_clear_path=True),
            ],
            metadata={"family": "classic"},
        ),
        "king": PieceDefinition(
            type="king",
            display_name="King",
            symbols={"white": "\u2654", "black": "\u265A"},
            points=DEFAULT_PIECE_POINTS["king"],
            is_custom=False,
            custom_attributes={},
            patterns=[
                MovePattern(dr=1, dc=0),
                MovePattern(dr=-1, dc=0),
                MovePattern(dr=0, dc=1),
                MovePattern(dr=0, dc=-1),
                MovePattern(dr=1, dc=1),
                MovePattern(dr=1, dc=-1),
                MovePattern(dr=-1, dc=1),
                MovePattern(dr=-1, dc=-1),
            ],
            metadata={"family": "classic"},
        ),
    }


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
        classic_back_rank = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"]
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
            grid[0][col] = _create_piece_instance(black_back_rank[index], "black", piece_definitions)

    if board_rows >= 2:
        for col in piece_columns:
            grid[1][col] = _create_piece_instance("pawn", "black", piece_definitions)

    if board_rows >= 2:
        for col in piece_columns:
            grid[board_rows - 2][col] = _create_piece_instance("pawn", "white", piece_definitions)

    if board_rows >= 1:
        for index, col in enumerate(piece_columns):
            grid[board_rows - 1][col] = _create_piece_instance(white_back_rank[index], "white", piece_definitions)

    return board


def _normalize_placement(
    placement: BoardPlacement,
    board_rows: int,
    board_cols: int,
    piece_definitions: dict[str, PieceDefinition],
) -> BoardPlacement:
    if placement.type not in piece_definitions:
        raise HTTPException(status_code=400, detail=f"Unknown piece type: {placement.type}")
    if placement.color not in {"white", "black"}:
        raise HTTPException(status_code=400, detail=f"Unsupported piece color: {placement.color}")
    if placement.row < 0 or placement.row >= board_rows or placement.col < 0 or placement.col >= board_cols:
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
        self.repository = repository or GameRepository()

    def _load_game(self, game_id: str) -> GameRecord:
        try:
            record = self.repository.get_game(game_id)
        except ExpiredGameError as error:
            raise HTTPException(status_code=410, detail=str(error)) from error

        if record is None:
            raise HTTPException(status_code=404, detail="Game not found")

        _sync_piece_metadata(record.state)
        self.engine.evaluate_state(record.state)
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
    ) -> GameRecord:
        try:
            return self.repository.save_game(state, expected_version, audit)
        except ConcurrentUpdateError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @staticmethod
    def _invite_url(invite_token: str) -> str:
        return f"{get_settings().frontend_url}/join/{invite_token}"

    def create_game(self, request: CreateGameRequest) -> GameSessionResponse:
        piece_definitions = build_default_piece_definitions()
        for custom_piece in request.customPieces:
            definition = _piece_definition_from_payload(custom_piece)
            piece_definitions[definition.type] = definition

        rule_settings = _apply_rule_patches(
            settings=self.engine.default_rule_settings(),
            patches=request.rules,
            engine=self.engine,
        )

        game_state = GameState(
            id=str(uuid.uuid4()),
            board=_initial_board(request.boardRows, request.boardCols, piece_definitions),
            current_player="white",
            rules=rule_settings,
            piece_definitions=piece_definitions,
            history=[],
            captured_pieces={"white": [], "black": []},
            winner=None,
            game_status="active",
            score={"white": 0, "black": 0},
        )

        self.engine.evaluate_state(game_state)

        settings = get_settings()
        now = datetime.now(timezone.utc)
        game_expires_at = now + timedelta(days=settings.game_ttl_days)

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
        invite_token = generate_token()
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
            game=self.serialize_game(record),
            playerToken=host_token,
            playerColor="white",
            role="host",
            inviteToken=invite_token,
            inviteUrl=self._invite_url(invite_token),
            inviteExpiresAt=invite_expires_at,
        )

    def join_game(self, request: JoinGameRequest) -> GameSessionResponse:
        player_token = generate_token()
        try:
            record = self.repository.claim_invite(
                hash_token(request.inviteToken),
                hash_token(player_token),
            )
        except InviteClaimError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        return GameSessionResponse(
            game=self.serialize_game(record),
            playerToken=player_token,
            playerColor="black",
            role="player",
        )

    def get_game(self, game_id: str, player_token: str | None = None) -> GameRecord:
        return self.authorize(game_id, player_token).record

    def replace_invite(self, game_id: str, player_token: str | None) -> InviteResponse:
        authorized = self.authorize(game_id, player_token, require_host=True)
        if authorized.record.ready:
            raise HTTPException(status_code=409, detail="This game already has two players")

        invite_token = generate_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=get_settings().invite_ttl_hours
        )
        self.repository.replace_invite(game_id, hash_token(invite_token), expires_at)
        return InviteResponse(
            inviteToken=invite_token,
            inviteUrl=self._invite_url(invite_token),
            inviteExpiresAt=expires_at,
        )

    def move_piece(
        self,
        game_id: str,
        request: MoveRequest,
        player_token: str | None = None,
    ) -> tuple[GameRecord, str]:
        authorized = self.authorize(game_id, player_token)
        record = authorized.record
        game_state = record.state

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
        expected_version = self._expected_version(record, request.expectedVersion)

        for patch in request.pieces:
            _apply_piece_patch(game_state.piece_definitions, patch)

        _sync_piece_metadata(game_state)
        self.engine.evaluate_state(game_state)
        return self._save(game_state, expected_version)

    def reset_game(
        self,
        game_id: str,
        request: ResetGameRequest,
        player_token: str | None = None,
    ) -> GameRecord:
        authorized = self.authorize(game_id, player_token, require_host=True)
        record = authorized.record
        game_state = record.state
        expected_version = self._expected_version(record, request.expectedVersion)
        board_rows = request.boardRows if request.boardRows is not None else game_state.board.rows
        board_cols = request.boardCols if request.boardCols is not None else game_state.board.cols

        game_state.board = _initial_board(board_rows, board_cols, game_state.piece_definitions)
        game_state.current_player = "white"
        game_state.history = []
        game_state.captured_pieces = {"white": [], "black": []}
        game_state.winner = None
        game_state.game_status = "active"
        game_state.score = {"white": 0, "black": 0}

        self.engine.evaluate_state(game_state)
        return self._save(game_state, expected_version)

    def update_board_layout(
        self,
        game_id: str,
        request: UpdateBoardLayoutRequest,
        player_token: str | None = None,
    ) -> GameRecord:
        authorized = self.authorize(game_id, player_token, require_host=True)
        record = authorized.record
        game_state = record.state
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

        self.engine.evaluate_state(game_state)
        return self._save(game_state, expected_version)

    def serialize_game(
        self,
        record: GameRecord,
        last_explanation: str | None = None,
    ) -> GameResponse:
        game_state = record.state

        def piece_view(piece: Piece) -> PieceView:
            definition = game_state.piece_definitions.get(piece.type)
            symbol = definition.symbols[piece.color] if definition else "?"
            return PieceView(
                type=piece.type,
                name=piece.name,
                color=piece.color,
                points=piece.points,
                symbol=symbol,
                hasMoved=piece.has_moved,
                isCustom=piece.is_custom,
                customAttributes=piece.custom_attributes,
            )

        board_view: list[list[PieceView | None]] = []
        for row in game_state.board.grid:
            board_view.append([piece_view(piece) if piece is not None else None for piece in row])

        valid_moves = (
            self.engine.get_valid_moves_for_current_player(game_state) if record.ready else []
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
        rule_views = []
        for rule in self.engine.available_rules():
            setting = settings_map.get(rule.id, RuleSetting(id=rule.id, enabled=True, params={}))
            rule_views.append(
                RuleView(
                    id=rule.id,
                    name=rule.name,
                    description=rule.description,
                    tier=rule.tier,
                    enabled=True if not rule.can_disable else setting.enabled,
                    canDisable=rule.can_disable,
                    params=setting.params,
                )
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
                    },
                )
            )

        captured_pieces_view = {
            color: [piece_view(piece) for piece in pieces]
            for color, pieces in game_state.captured_pieces.items()
        }

        if last_explanation is None and game_state.history:
            last_explanation = game_state.history[-1].explanation

        return GameResponse(
            id=game_state.id,
            mode=record.mode,
            version=record.version,
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
                    customAttributes=definition.custom_attributes,
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
        )
