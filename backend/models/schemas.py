from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Position(BaseModel):
    row: int
    col: int


class PieceView(BaseModel):
    type: str
    name: str
    color: str
    points: int | None = None
    symbol: str
    hasMoved: bool
    isCustom: bool = False
    customAttributes: dict[str, Any] = Field(default_factory=dict)


class CaptureView(BaseModel):
    row: int
    col: int
    piece: PieceView
    reason: str | None = None


class ValidMoveView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_pos: Position = Field(alias="from")
    to: Position
    captures: list[CaptureView] = Field(default_factory=list)
    explanation: str = ""


class RuleView(BaseModel):
    id: str
    name: str
    description: str
    tier: str
    enabled: bool
    canDisable: bool
    params: dict[str, Any] = Field(default_factory=dict)


class MoveHistoryView(BaseModel):
    moveNumber: int
    player: str
    piece: str
    from_pos: Position = Field(alias="from")
    to: Position
    captures: list[CaptureView] = Field(default_factory=list)
    explanation: str


class MovePatternView(BaseModel):
    dr: int
    dc: int
    repeat: bool = False
    mode: str = "both"
    relative_to_color: bool = True
    requires_unmoved: bool = False
    requires_clear_path: bool = False


class PieceDefinitionView(BaseModel):
    type: str
    displayName: str
    symbols: dict[str, str]
    points: int | None = None
    isCustom: bool = False
    customAttributes: dict[str, Any] = Field(default_factory=dict)
    patterns: list[MovePatternView] = Field(default_factory=list)


class GameResponse(BaseModel):
    id: str
    mode: Literal["local", "online"]
    version: int
    ready: bool
    players: dict[str, str]
    boardRows: int
    boardCols: int
    boardSize: int
    board: list[list[PieceView | None]]
    currentPlayer: str
    validMoves: list[ValidMoveView]
    rules: list[RuleView]
    pieceDefinitions: list[PieceDefinitionView]
    history: list[MoveHistoryView]
    capturedPieces: dict[str, list[PieceView]]
    lastMoveExplanation: str | None = None
    winner: str | None = None
    gameStatus: str
    score: dict[str, int]


class RulePatch(BaseModel):
    id: str
    enabled: bool | None = None
    params: dict[str, Any] | None = None


class MovePatternPayload(BaseModel):
    dr: int
    dc: int
    repeat: bool = False
    mode: str = "both"
    relative_to_color: bool = True
    requires_unmoved: bool = False
    requires_clear_path: bool = False


class PieceDefinitionPayload(BaseModel):
    type: str
    displayName: str
    symbols: dict[str, str]
    patterns: list[MovePatternPayload]
    points: int | None = None
    isCustom: bool = True
    customAttributes: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateGameRequest(BaseModel):
    mode: Literal["local", "online"] = "local"
    boardSize: int | None = Field(default=None, ge=4, le=16)
    boardRows: int = Field(default=8, ge=4, le=16)
    boardCols: int = Field(default=8, ge=4, le=16)
    rules: list[RulePatch] = Field(default_factory=list, max_length=128)
    customPieces: list[PieceDefinitionPayload] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def normalize_dimensions(self) -> "CreateGameRequest":
        if self.boardSize is not None:
            self.boardRows = self.boardSize
            self.boardCols = self.boardSize
        return self


class MoveRequest(BaseModel):
    fromRow: int
    fromCol: int
    toRow: int
    toCol: int
    expectedVersion: int | None = Field(default=None, ge=1)


class UpdateRulesRequest(BaseModel):
    rules: list[RulePatch] = Field(max_length=128)
    expectedVersion: int | None = Field(default=None, ge=1)


class PieceDefinitionPatch(BaseModel):
    type: str
    displayName: str | None = None
    symbols: dict[str, str] | None = None
    patterns: list[MovePatternPayload] | None = None
    points: int | None = None
    isCustom: bool | None = None
    customAttributes: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class UpdatePiecesRequest(BaseModel):
    pieces: list[PieceDefinitionPatch] = Field(max_length=64)
    expectedVersion: int | None = Field(default=None, ge=1)


class ResetGameRequest(BaseModel):
    boardSize: int | None = Field(default=None, ge=4, le=16)
    boardRows: int | None = Field(default=None, ge=4, le=16)
    boardCols: int | None = Field(default=None, ge=4, le=16)
    expectedVersion: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def normalize_dimensions(self) -> "ResetGameRequest":
        if self.boardSize is not None:
            self.boardRows = self.boardSize
            self.boardCols = self.boardSize
        return self


class BoardPlacement(BaseModel):
    row: int
    col: int
    type: str
    color: str


class UpdateBoardLayoutRequest(BaseModel):
    boardRows: int | None = Field(default=None, ge=4, le=16)
    boardCols: int | None = Field(default=None, ge=4, le=16)
    placements: list[BoardPlacement] = Field(default_factory=list, max_length=256)
    expectedVersion: int | None = Field(default=None, ge=1)


class JoinGameRequest(BaseModel):
    inviteToken: str = Field(min_length=20, max_length=256)


class GameSessionResponse(BaseModel):
    game: GameResponse
    playerToken: str | None = None
    playerColor: str | None = None
    role: str
    inviteToken: str | None = None
    inviteUrl: str | None = None
    inviteExpiresAt: datetime | None = None


class InviteResponse(BaseModel):
    inviteToken: str
    inviteUrl: str
    inviteExpiresAt: datetime
