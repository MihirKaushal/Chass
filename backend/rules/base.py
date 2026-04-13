from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from backend.models import CaptureEvent, GameState, Move, MoveOption, Piece


@dataclass
class ValidationResult:
    is_valid: bool
    reason: str | None = None


@dataclass
class RuleContext:
    captures: list[CaptureEvent] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    moved_piece: Piece | None = None
    target_piece: Piece | None = None
    simulated: bool = False

    def add_capture(
        self,
        row: int,
        col: int,
        piece: Piece,
        reason: str | None = None,
    ) -> None:
        self.captures.append(CaptureEvent(row=row, col=col, piece=piece, reason=reason))


class MovementHelper(Protocol):
    def generate_piece_moves(
        self, state: GameState, row: int, col: int
    ) -> list[MoveOption]: ...

    def get_valid_moves_for_color(
        self, state: GameState, color: str
    ) -> list[MoveOption]: ...

    def is_king_in_check(self, state: GameState, color: str) -> bool: ...

    def find_king(self, state: GameState, color: str) -> tuple[int, int] | None: ...

    def simulate_move_for_validation(self, state: GameState, move: Move) -> GameState: ...


class Rule:
    id: str = "base_rule"
    name: str = "Base Rule"
    description: str = ""
    tier: str = "basic"
    can_disable: bool = True
    apply_in_simulation: bool = True

    def validate(
        self,
        state: GameState,
        move: Move,
        helper: MovementHelper,
        params: dict,
    ) -> ValidationResult:
        return ValidationResult(is_valid=True)

    def apply(
        self,
        state: GameState,
        move: Move,
        context: RuleContext,
        helper: MovementHelper,
        params: dict,
    ) -> None:
        return None

    def evaluate_state(
        self,
        state: GameState,
        helper: MovementHelper,
        params: dict,
    ) -> None:
        return None
