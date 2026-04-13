from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Color = Literal["white", "black"]
MoveMode = Literal["move", "capture", "both"]
GameStatus = Literal["active", "check", "checkmate", "stalemate"]


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
    size: int
    grid: list[list[Piece | None]]

    @model_validator(mode="after")
    def validate_grid_shape(self) -> "Board":
        if self.size < 4:
            raise ValueError("Board size must be at least 4")
        if len(self.grid) != self.size:
            raise ValueError("Board grid row count must match board size")
        for row in self.grid:
            if len(row) != self.size:
                raise ValueError("Board grid column count must match board size")
        return self

    def to_square_grid(self) -> list[list[Square]]:
        squares: list[list[Square]] = []
        for row_idx in range(self.size):
            row_squares: list[Square] = []
            for col_idx in range(self.size):
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


class MoveOption(BaseModel):
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    captures: list[CaptureEvent] = Field(default_factory=list)
    explanation: str = ""


class GameState(BaseModel):
    id: str
    board: Board
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
