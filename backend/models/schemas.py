from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    boardSize: int = Field(default=8, ge=4, le=16)
    rules: list[RulePatch] = Field(default_factory=list)
    customPieces: list[PieceDefinitionPayload] = Field(default_factory=list)


class MoveRequest(BaseModel):
    fromRow: int
    fromCol: int
    toRow: int
    toCol: int


class UpdateRulesRequest(BaseModel):
    rules: list[RulePatch]


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
    pieces: list[PieceDefinitionPatch]


class ResetGameRequest(BaseModel):
    boardSize: int | None = Field(default=None, ge=4, le=16)
