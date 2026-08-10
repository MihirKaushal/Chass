from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Color = Literal["white", "black"]
MoveMode = Literal["move", "capture", "both"]
GameStatus = Literal["active", "check", "checkmate", "stalemate", "score_target"]
GameVariant = Literal["classic", "gambit"]
GamePhase = Literal["lobby", "deployment", "handoff", "play", "finished"]


class MovePattern(BaseModel):
    dr: int
    dc: int
    repeat: bool = False
    mode: MoveMode = "both"
    relative_to_color: bool = True
    requires_unmoved: bool = False
    requires_clear_path: bool = False


class PieceDefinition(BaseModel):
    type: str
    display_name: str
    symbols: dict[Color, str]
    patterns: list[MovePattern]
    points: int | None = None
    is_custom: bool = False
    custom_attributes: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Piece(BaseModel):
    type: str
    name: str = ""
    color: Color
    points: int | None = None
    has_moved: bool = False
    is_custom: bool = False
    custom_attributes: dict[str, Any] = Field(default_factory=dict)


class Square(BaseModel):
    row: int
    col: int
    is_light: bool
    piece: Piece | None = None


class Board(BaseModel):
    rows: int
    cols: int
    grid: list[list[Piece | None]]

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_size(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        if "rows" in value and "cols" in value:
            return value
        legacy_size = value.get("size")
        if legacy_size is None:
            return value
        migrated = dict(value)
        migrated["rows"] = legacy_size
        migrated["cols"] = legacy_size
        return migrated

    @model_validator(mode="after")
    def validate_grid_shape(self) -> "Board":
        if self.rows < 4 or self.cols < 4:
            raise ValueError("Board dimensions must be at least 4x4")
        if len(self.grid) != self.rows:
            raise ValueError("Board grid row count must match board rows")
        for row in self.grid:
            if len(row) != self.cols:
                raise ValueError("Board grid column count must match board cols")
        return self

    @property
    def size(self) -> int:
        # Compatibility shim for legacy code that still expects square board size.
        return max(self.rows, self.cols)

    def to_square_grid(self) -> list[list[Square]]:
        squares: list[list[Square]] = []
        for row_idx in range(self.rows):
            row_squares: list[Square] = []
            for col_idx in range(self.cols):
                row_squares.append(
                    Square(
                        row=row_idx,
                        col=col_idx,
                        is_light=((row_idx + col_idx) % 2 == 0),
                        piece=self.grid[row_idx][col_idx],
                    )
                )
            squares.append(row_squares)
        return squares


class Move(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_row: int = Field(alias="fromRow")
    from_col: int = Field(alias="fromCol")
    to_row: int = Field(alias="toRow")
    to_col: int = Field(alias="toCol")
    promotion: Literal["queen", "rook", "bishop", "knight"] | None = None


class RuleSetting(BaseModel):
    id: str
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class CaptureEvent(BaseModel):
    row: int
    col: int
    piece: Piece
    reason: str | None = None


class MoveRecord(BaseModel):
    move_number: int
    player: Color
    piece: str
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    captures: list[CaptureEvent] = Field(default_factory=list)
    explanation: str
    action_type: str = "move"


class MoveOption(BaseModel):
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    captures: list[CaptureEvent] = Field(default_factory=list)
    explanation: str = ""


class BoardCoordinate(BaseModel):
    row: int
    col: int


class DeploymentPiece(BaseModel):
    row: int
    col: int
    type: str


class GambitConfig(BaseModel):
    budget: int = 39
    max_pieces: int = 16
    setup_rows: int = 2
    command_point_cap: int = 3
    piece_points: dict[str, int] = Field(
        default_factory=lambda: {
            "pawn": 1,
            "knight": 3,
            "bishop": 3,
            "rook": 5,
            "queen": 9,
            "king": 0,
        }
    )
    piece_caps: dict[str, int] = Field(
        default_factory=lambda: {
            "pawn": 12,
            "knight": 4,
            "bishop": 4,
            "rook": 4,
            "queen": 2,
            "king": 1,
        }
    )
    power_costs: dict[str, int] = Field(
        default_factory=lambda: {
            "reinforce": 1,
            "evolve": 2,
            "stronghold": 3,
        }
    )
    power_usage_caps: dict[str, int] = Field(
        default_factory=lambda: {
            "reinforce": 2,
            "evolve": 2,
            "stronghold": 1,
        }
    )
    affinity_squares: dict[Color, list[BoardCoordinate]] = Field(
        default_factory=lambda: {
            "white": [
                BoardCoordinate(row=4, col=4),  # e4
                BoardCoordinate(row=3, col=3),  # d5
            ],
            "black": [
                BoardCoordinate(row=4, col=3),  # d4
                BoardCoordinate(row=3, col=4),  # e5
            ],
        }
    )


class GambitState(BaseModel):
    config: GambitConfig = Field(default_factory=GambitConfig)
    deployments: dict[Color, list[DeploymentPiece]] = Field(
        default_factory=lambda: {"white": [], "black": []}
    )
    deployment_ready: dict[Color, bool] = Field(
        default_factory=lambda: {"white": False, "black": False}
    )
    deployment_undo: dict[Color, list[list[DeploymentPiece]]] = Field(
        default_factory=lambda: {"white": [], "black": []}
    )
    deployment_versions: dict[Color, int] = Field(
        default_factory=lambda: {"white": 1, "black": 1}
    )
    active_deployment_color: Color = "white"
    command_points: dict[Color, int] = Field(
        default_factory=lambda: {"white": 0, "black": 0}
    )
    affinity_primed: dict[Color, bool] = Field(
        default_factory=lambda: {"white": False, "black": False}
    )
    power_usage: dict[Color, dict[str, int]] = Field(
        default_factory=lambda: {
            "white": {"reinforce": 0, "evolve": 0, "stronghold": 0},
            "black": {"reinforce": 0, "evolve": 0, "stronghold": 0},
        }
    )
    setup_message: str | None = None
    last_power_explanation: str | None = None


class GameState(BaseModel):
    id: str
    board: Board
    variant: GameVariant = "classic"
    phase: GamePhase = "play"
    gambit: GambitState | None = None
    current_player: Color = "white"
    rules: list[RuleSetting] = Field(default_factory=list)
    piece_definitions: dict[str, PieceDefinition] = Field(default_factory=dict)
    history: list[MoveRecord] = Field(default_factory=list)
    captured_pieces: dict[str, list[Piece]] = Field(
        default_factory=lambda: {"white": [], "black": []}
    )
    winner: Color | None = None
    game_status: GameStatus = "active"
    score: dict[Color, int] = Field(default_factory=lambda: {"white": 0, "black": 0})

    def clone(self) -> "GameState":
        return self.model_copy(deep=True)
