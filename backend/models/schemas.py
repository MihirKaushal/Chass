from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Position(BaseModel):
    row: int
    col: int


class PieceView(BaseModel):
    pieceId: str
    type: str
    name: str
    color: str
    points: int | None = None
    symbol: str
    hasMoved: bool
    isCustom: bool = False
    icon: str = ""
    description: str = ""
    movement: str = ""
    customAttributes: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)


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
    isSpecial: bool = False
    params: dict[str, Any] = Field(default_factory=dict)


class MoveHistoryView(BaseModel):
    moveNumber: int
    player: str
    piece: str
    from_pos: Position = Field(alias="from")
    to: Position
    captures: list[CaptureView] = Field(default_factory=list)
    explanation: str
    actionType: str = "move"


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
    icon: str = ""
    description: str = ""
    movement: str = ""
    behavior: str = "patterns"
    customAttributes: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    patterns: list[MovePatternView] = Field(default_factory=list)


class GambitConfigView(BaseModel):
    budget: int
    maxPieces: int
    setupRows: int
    commandPointCap: int
    affinityEnabled: bool = True
    requireExactBudget: bool = False
    draftEnabled: bool = False
    draftPool: dict[str, int] = Field(default_factory=dict)
    piecePoints: dict[str, int]
    pieceCaps: dict[str, int]
    powerCosts: dict[str, int]
    powerUsageCaps: dict[str, int]
    affinitySquares: dict[str, list[Position]]


class GambitSetupSummaryView(BaseModel):
    pointsSpent: int
    pointsRemaining: int
    pieceCount: int
    counts: dict[str, int]
    canReady: bool
    issues: list[str] = Field(default_factory=list)


class GambitDraftPlayerView(BaseModel):
    pointsSpent: int
    pointsRemaining: int
    pieceCount: int
    counts: dict[str, int]
    hasKing: bool


class GambitView(BaseModel):
    config: GambitConfigView
    viewerColor: str | None = None
    editableColor: str | None = None
    deploymentReady: dict[str, bool]
    setupSummary: GambitSetupSummaryView | None = None
    setupMessage: str | None = None
    commandPoints: dict[str, int]
    affinityPrimed: dict[str, bool]
    affinityControlled: dict[str, bool]
    powerUsage: dict[str, dict[str, int]]
    legalPowerTargets: dict[str, list[Position]]
    lastPowerExplanation: str | None = None
    draftActiveColor: str = "white"
    draftPicks: dict[str, list[str]] = Field(default_factory=dict)
    draftPoolRemaining: dict[str, int] = Field(default_factory=dict)
    draftPassed: dict[str, bool] = Field(default_factory=dict)
    draftSummary: dict[str, GambitDraftPlayerView] = Field(default_factory=dict)
    draftOptions: list[str] = Field(default_factory=list)
    draftCanAct: bool = False
    draftCanPass: bool = False


class AffinityView(BaseModel):
    enabled: bool = False
    commandPointCap: int = 3
    powerCosts: dict[str, int] = Field(default_factory=dict)
    powerUsageCaps: dict[str, int] = Field(default_factory=dict)
    squares: dict[str, list[Position]] = Field(default_factory=dict)
    commandPoints: dict[str, int] = Field(default_factory=dict)
    primed: dict[str, bool] = Field(default_factory=dict)
    controlled: dict[str, bool] = Field(default_factory=dict)
    powerUsage: dict[str, dict[str, int]] = Field(default_factory=dict)
    legalPowerTargets: dict[str, list[Position]] = Field(default_factory=dict)
    lastPowerExplanation: str | None = None


class CenterDominionView(BaseModel):
    targetRounds: int
    progress: dict[str, int]
    primed: dict[str, bool]
    controlled: dict[str, bool]
    squares: dict[str, list[Position]]


class CountdownView(BaseModel):
    id: str
    owner: str
    kind: str
    icon: str = ""
    label: str
    description: str
    remainingTurns: int
    pieceId: str | None = None
    pieceName: str | None = None


class AvailableActionView(BaseModel):
    id: str
    actionType: str
    owner: str
    icon: str = ""
    label: str
    description: str
    source: Position | None = None
    target: Position | None = None
    secondary: Position | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class AbilityStateView(BaseModel):
    enabled: bool = False
    allowed: list[str] = Field(default_factory=list)
    maxPerPlayer: int = 1
    selected: dict[str, list[str]] = Field(default_factory=dict)
    used: dict[str, dict[str, bool]] = Field(default_factory=dict)
    usageCount: dict[str, dict[str, int]] = Field(default_factory=dict)
    cooldowns: dict[str, dict[str, int]] = Field(default_factory=dict)
    viewerSelection: list[str] = Field(default_factory=list)
    editableColor: str | None = None


class ResultView(BaseModel):
    reasonCode: str
    description: str
    trigger: str
    winner: str | None = None


class ClockView(BaseModel):
    initialSeconds: int
    remainingSeconds: dict[str, float]
    activeColor: str
    turnStartedAt: datetime


class RematchView(BaseModel):
    status: Literal["idle", "pending"] = "idle"
    requestedBy: str | None = None
    approvals: dict[str, bool] = Field(default_factory=dict)
    canRespondAs: str | None = None


class GameResponse(BaseModel):
    id: str
    mode: Literal["local", "online"]
    variant: Literal["classic", "gambit"] = "classic"
    phase: Literal[
        "lobby",
        "ability_selection",
        "draft",
        "deployment",
        "handoff",
        "play",
        "finished",
    ] = "play"
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
    spentScore: dict[str, int] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)
    abilities: AbilityStateView = Field(default_factory=AbilityStateView)
    countdowns: list[CountdownView] = Field(default_factory=list)
    availableActions: list[AvailableActionView] = Field(default_factory=list)
    result: ResultView | None = None
    clock: ClockView | None = None
    gambit: GambitView | None = None
    affinity: AffinityView = Field(default_factory=AffinityView)
    centerDominion: CenterDominionView | None = None
    rematch: RematchView = Field(default_factory=RematchView)


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
    points: int | None = Field(default=None, ge=0)
    isCustom: bool = True
    customAttributes: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConfigurationPlacement(BaseModel):
    row: int
    col: int
    type: str
    color: Literal["white", "black", "neutral"]


class VictoryConfigPayload(BaseModel):
    mode: Literal[
        "checkmate",
        "king_capture",
        "timed",
        "point_race",
        "elimination",
        "royal_score",
        "center_dominion",
    ] = "checkmate"
    targetPoints: int = Field(default=21, ge=1, le=100000)
    timeSeconds: int = Field(default=600, ge=30, le=86400)
    kingPoints: int = Field(default=0, ge=0, le=100000)
    dominionRounds: int = Field(default=3, ge=1, le=20)


class SpecialAbilityConfigPayload(BaseModel):
    enabled: bool = False
    maxPerPlayer: int = Field(default=1, ge=1, le=6)
    allowed: list[
        Literal[
            "necromancy",
            "getaway",
            "eye_for_an_eye",
            "kamikaze",
            "episcopal",
            "power_of_love",
        ]
    ] = Field(default_factory=list)


class CustomRulesConfigPayload(BaseModel):
    affinityEnabled: bool = False
    commandPointCap: int = Field(default=3, ge=0, le=20)


class GambitConfigPayload(BaseModel):
    enabled: bool = False
    budget: int = Field(default=39, ge=0, le=100000)
    maxPieces: int = Field(default=16, ge=1, le=128)
    setupRows: int = Field(default=2, ge=1, le=8)
    maxQueens: int = Field(default=2, ge=0, le=32)
    # Legacy aliases retained so saved configurations continue to load.
    affinityEnabled: bool | None = None
    commandPointCap: int | None = Field(default=None, ge=0, le=20)
    pieceCaps: dict[str, int] = Field(default_factory=dict)
    draftEnabled: bool = False
    draftPool: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_piece_caps(self) -> "GambitConfigPayload":
        if any(value < 0 for value in self.pieceCaps.values()):
            raise ValueError("Piece limits cannot be negative")
        if any(value < 0 for value in self.draftPool.values()):
            raise ValueError("Draft pool counts cannot be negative")
        if any(value > 256 for value in self.draftPool.values()):
            raise ValueError("Draft pool counts cannot exceed 256")
        return self


class GameConfigurationPayload(BaseModel):
    schemaVersion: int = 2
    presetId: str = "custom"
    formationId: str = "custom"
    barricadeCount: int = Field(default=1, ge=0, le=8)
    enabledPieces: list[str] = Field(
        default_factory=lambda: ["pawn", "knight", "bishop", "rook", "queen", "king"],
        min_length=1,
        max_length=64,
    )
    piecePoints: dict[str, int | None] = Field(default_factory=dict)
    initialLayout: list[ConfigurationPlacement] = Field(default_factory=list, max_length=256)
    victory: VictoryConfigPayload = Field(default_factory=VictoryConfigPayload)
    customRules: CustomRulesConfigPayload = Field(default_factory=CustomRulesConfigPayload)
    specialAbilities: SpecialAbilityConfigPayload = Field(
        default_factory=SpecialAbilityConfigPayload
    )
    gambit: GambitConfigPayload = Field(default_factory=GambitConfigPayload)

    @model_validator(mode="after")
    def validate_points(self) -> "GameConfigurationPayload":
        if any(value is not None and value < 0 for value in self.piecePoints.values()):
            raise ValueError("Piece points cannot be negative")
        if any(value is not None and value > 100000 for value in self.piecePoints.values()):
            raise ValueError("Piece points cannot exceed 100000")
        return self


class CreateGameRequest(BaseModel):
    mode: Literal["local", "online"] = "local"
    variant: Literal["classic", "gambit"] = "classic"
    boardSize: int | None = Field(default=None, ge=4, le=16)
    boardRows: int = Field(default=8, ge=4, le=16)
    boardCols: int = Field(default=8, ge=4, le=16)
    rules: list[RulePatch] = Field(default_factory=list, max_length=128)
    customPieces: list[PieceDefinitionPayload] = Field(default_factory=list, max_length=64)
    configuration: GameConfigurationPayload | None = None

    @model_validator(mode="after")
    def normalize_dimensions(self) -> "CreateGameRequest":
        if self.boardSize is not None:
            self.boardRows = self.boardSize
            self.boardCols = self.boardSize
        if self.configuration and self.configuration.gambit.enabled:
            gambit = self.configuration.gambit
            if gambit.setupRows > self.boardRows // 2:
                raise ValueError("Gambit setup rows cannot cross the board midpoint")
            if gambit.maxPieces > gambit.setupRows * self.boardCols:
                raise ValueError("Gambit deployment rows do not have enough squares")
        return self


class MoveRequest(BaseModel):
    fromRow: int
    fromCol: int
    toRow: int
    toCol: int
    promotion: Literal["queen", "rook", "bishop", "knight", "kamikaze"] | None = None
    expectedVersion: int | None = Field(default=None, ge=1)


class GambitDeploymentRequest(BaseModel):
    action: Literal["place", "remove", "clear", "undo"]
    row: int | None = None
    col: int | None = None
    pieceType: str | None = None
    expectedVersion: int | None = Field(default=None, ge=1)


class GambitDraftRequest(BaseModel):
    action: Literal["pick", "pass"]
    pieceType: str | None = None
    expectedVersion: int | None = Field(default=None, ge=1)


class GambitReadyRequest(BaseModel):
    expectedVersion: int | None = Field(default=None, ge=1)


class GambitHandoffRequest(BaseModel):
    expectedVersion: int | None = Field(default=None, ge=1)


class GambitPowerRequest(BaseModel):
    power: Literal["reinforce", "evolve", "stronghold"]
    row: int
    col: int
    evolveTo: Literal["knight", "bishop"] | None = None
    expectedVersion: int | None = Field(default=None, ge=1)


class GameActionRequest(BaseModel):
    actionType: Literal[
        "catapult_projectile",
        "demolish_barricade",
        "move_barricade",
        "necromancy",
        "getaway",
        "eye_for_an_eye",
        "episcopal",
    ]
    source: Position | None = None
    target: Position | None = None
    secondary: Position | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    expectedVersion: int | None = Field(default=None, ge=1)


class AbilitySelectionRequest(BaseModel):
    abilityIds: list[Literal[
        "necromancy",
        "getaway",
        "eye_for_an_eye",
        "kamikaze",
        "episcopal",
        "power_of_love",
    ]] | None = Field(default=None, min_length=1, max_length=6)
    abilityId: Literal[
        "necromancy",
        "getaway",
        "eye_for_an_eye",
        "kamikaze",
        "episcopal",
        "power_of_love",
    ] | None = None
    expectedVersion: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def normalize_selection(self) -> "AbilitySelectionRequest":
        if self.abilityIds is None:
            if self.abilityId is None:
                raise ValueError("Choose at least one ability")
            self.abilityIds = [self.abilityId]
        if len(set(self.abilityIds)) != len(self.abilityIds):
            raise ValueError("Ability choices must be unique")
        return self


class SetupHandoffRequest(BaseModel):
    expectedVersion: int | None = Field(default=None, ge=1)


class UpdateRulesRequest(BaseModel):
    rules: list[RulePatch] = Field(max_length=128)
    expectedVersion: int | None = Field(default=None, ge=1)


class PieceDefinitionPatch(BaseModel):
    type: str
    displayName: str | None = None
    symbols: dict[str, str] | None = None
    patterns: list[MovePatternPayload] | None = None
    points: int | None = Field(default=None, ge=0)
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


class RematchRequest(BaseModel):
    action: Literal["request", "accept", "decline", "cancel"]
    color: Literal["white", "black"] | None = None
    expectedVersion: int | None = Field(default=None, ge=1)


class ConfigurationValidationResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    disabledOptions: dict[str, dict[str, str]] = Field(default_factory=dict)


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
    inviteToken: str | None = Field(default=None, min_length=8, max_length=256)
    inviteCode: str | None = Field(default=None, min_length=8, max_length=12)

    @model_validator(mode="after")
    def validate_invite_credential(self) -> "JoinGameRequest":
        if bool(self.inviteToken) == bool(self.inviteCode):
            raise ValueError("Provide either an invite link token or an invite code")
        return self


class GameSessionResponse(BaseModel):
    game: GameResponse
    playerToken: str | None = None
    playerColor: str | None = None
    role: str
    inviteToken: str | None = None
    inviteCode: str | None = None
    inviteUrl: str | None = None
    inviteExpiresAt: datetime | None = None


class InviteResponse(BaseModel):
    inviteToken: str
    inviteCode: str
    inviteUrl: str
    inviteExpiresAt: datetime
