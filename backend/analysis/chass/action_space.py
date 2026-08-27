from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.models import GameState, Move, MoveOption
from backend.rules import RuleEngine
from backend.rules.variant_system import has_ability

ActionKind = Literal["move", "custom", "command"]

ORDERING_VALUES = {
    "pawn": 1.0,
    "knight": 3.0,
    "bishop": 3.2,
    "rook": 5.0,
    "queen": 9.0,
    "king": 12.0,
    "maharani": 13.0,
    "catapult": 5.0,
    "hypnotizer": 6.0,
    "diplomat": 4.0,
    "cannibal": 6.0,
    "elephant": 7.0,
    "barricade": 1.0,
}

CUSTOM_ACTION_PRIORITY = {
    "getaway": 20.0,
    "catapult_projectile": 12.0,
    "eye_for_an_eye": 10.0,
    "necromancy": 8.0,
    "episcopal": 7.0,
    "demolish_barricade": 5.0,
    "scorch": 2.5,
    "move_barricade": 1.5,
}

COMMAND_PRIORITY = {
    "stronghold": 8.0,
    "evolve": 6.0,
    "reinforce": 4.0,
}


@dataclass(frozen=True)
class ChassAction:
    kind: ActionKind
    color: str
    key: str
    label: str
    ordering_score: float
    move: Move | None = None
    payload: dict | None = None
    power: str | None = None
    row: int | None = None
    col: int | None = None
    evolve_to: str | None = None

    def apply(self, state: GameState, engine: RuleEngine) -> GameState:
        if self.kind == "move" and self.move is not None:
            return engine.simulate_turn_move(state, self.move)
        if self.kind == "custom" and self.payload is not None:
            return engine.simulate_turn_action(state, self.color, self.payload)
        if (
            self.kind == "command"
            and self.power is not None
            and self.row is not None
            and self.col is not None
        ):
            return engine.simulate_command_power(
                state,
                self.color,
                power=self.power,
                row=self.row,
                col=self.col,
                evolve_to=self.evolve_to,
            )
        raise ValueError("Incomplete Chass analysis action")


def _capture_hint(option: MoveOption, color: str) -> float:
    score = 0.0
    for capture in option.captures:
        value = ORDERING_VALUES.get(capture.piece.type, 4.0)
        score += value if capture.piece.color != color else -value
    return score


def _center_hint(state: GameState, row: int | None, col: int | None) -> float:
    if row is None or col is None:
        return 0.0
    center_row = (state.board.rows - 1) / 2
    center_col = (state.board.cols - 1) / 2
    distance = abs(row - center_row) + abs(col - center_col)
    return max(0.0, 1.0 - (distance / max(1, state.board.rows + state.board.cols)))


def _promotion_choices(state: GameState, color: str) -> tuple[str | None, ...]:
    choices: list[str | None] = [
        piece_type
        for piece_type in ("queen", "rook", "bishop", "knight")
        if piece_type in state.piece_definitions
    ]
    if has_ability(state, color, "kamikaze"):
        choices.append("kamikaze")
    return tuple(choices or [None])


def _move_actions(state: GameState, color: str, engine: RuleEngine) -> list[ChassAction]:
    work_state = state.clone()
    work_state.current_player = color
    engine.evaluate_state(work_state)
    if work_state.winner is not None or work_state.phase == "finished":
        return []

    actions: list[ChassAction] = []
    for option in engine.get_valid_moves_for_color(work_state, color):
        piece = work_state.board.grid[option.from_row][option.from_col]
        if piece is None:
            continue
        promotion_row = 0 if color == "white" else work_state.board.rows - 1
        promotions = (
            _promotion_choices(work_state, color)
            if piece.type == "pawn" and option.to_row == promotion_row
            else (None,)
        )
        for promotion in promotions:
            move = Move(
                fromRow=option.from_row,
                fromCol=option.from_col,
                toRow=option.to_row,
                toCol=option.to_col,
                promotion=promotion,
            )
            # Ordinary options already passed RuleEngine validation. Promotion
            # variants still need their choice-specific validation.
            if promotion is not None and not engine.validate_move(work_state, move).is_valid:
                continue
            promotion_bonus = 0.0
            if promotion == "kamikaze":
                promotion_bonus = 11.0
            elif promotion:
                promotion_bonus = ORDERING_VALUES.get(promotion, 3.0)
            score = (
                _capture_hint(option, color) * 2.0
                + promotion_bonus
                + _center_hint(work_state, option.to_row, option.to_col)
            )
            actions.append(
                ChassAction(
                    kind="move",
                    color=color,
                    key=(
                        f"move:{option.from_row}:{option.from_col}:"
                        f"{option.to_row}:{option.to_col}:{promotion or '-'}"
                    ),
                    label=option.explanation or f"{piece.name} move",
                    ordering_score=score,
                    move=move,
                )
            )
    return actions


def _custom_actions(state: GameState, color: str, engine: RuleEngine) -> list[ChassAction]:
    work_state = state.clone()
    work_state.current_player = color
    engine.evaluate_state(work_state)
    if work_state.winner is not None or work_state.phase == "finished":
        return []

    actions: list[ChassAction] = []
    for payload in engine.get_available_actions(work_state, color):
        action_type = str(payload.get("actionType", "custom"))
        source = payload.get("source") or {}
        target = payload.get("target") or {}
        target_piece = None
        target_row = target.get("row")
        target_col = target.get("col")
        if isinstance(target_row, int) and isinstance(target_col, int):
            target_piece = work_state.board.grid[target_row][target_col]
        capture_bonus = (
            ORDERING_VALUES.get(target_piece.type, 4.0)
            if target_piece is not None and target_piece.color != color
            else 0.0
        )
        own_piece = None
        source_row = source.get("row")
        source_col = source.get("col")
        if isinstance(source_row, int) and isinstance(source_col, int):
            own_piece = work_state.board.grid[source_row][source_col]
        sacrifice_cost = (
            ORDERING_VALUES.get(own_piece.type, 4.0)
            if action_type in {"eye_for_an_eye", "demolish_barricade"}
            and own_piece is not None
            else 0.0
        )
        score = (
            CUSTOM_ACTION_PRIORITY.get(action_type, 1.0)
            + capture_bonus
            - (sacrifice_cost * 0.5)
            + _center_hint(work_state, target_row, target_col)
        )
        actions.append(
            ChassAction(
                kind="custom",
                color=color,
                key=f"custom:{payload.get('id', len(actions))}",
                label=str(payload.get("label", action_type.replace("_", " ").title())),
                ordering_score=score,
                payload=dict(payload),
            )
        )
    return actions


def _command_actions(state: GameState, color: str, engine: RuleEngine) -> list[ChassAction]:
    if not state.configuration.custom_rules.affinity_enabled:
        return []
    work_state = state.clone()
    work_state.current_player = color
    engine.evaluate_state(work_state)
    if work_state.winner is not None or work_state.phase == "finished":
        return []

    actions: list[ChassAction] = []
    for power, targets in engine.gambit.legal_power_targets(
        work_state,
        color,
        engine,
    ).items():
        for target in targets:
            choices = ("knight", "bishop") if power == "evolve" else (None,)
            for evolve_to in choices:
                row, col = int(target["row"]), int(target["col"])
                actions.append(
                    ChassAction(
                        kind="command",
                        color=color,
                        key=f"command:{power}:{row}:{col}:{evolve_to or '-'}",
                        label=power.title(),
                        ordering_score=(
                            COMMAND_PRIORITY.get(power, 2.0)
                            + _center_hint(work_state, row, col)
                        ),
                        power=power,
                        row=row,
                        col=col,
                        evolve_to=evolve_to,
                    )
                )
    return actions


def legal_turn_actions(
    state: GameState,
    engine: RuleEngine,
    *,
    limit: int | None = None,
) -> list[ChassAction]:
    if state.phase != "play" or state.winner is not None:
        return []
    color = state.current_player
    actions = [
        *_move_actions(state, color, engine),
        *_custom_actions(state, color, engine),
        *_command_actions(state, color, engine),
    ]
    actions.sort(key=lambda action: (-action.ordering_score, action.key))
    return actions if limit is None else actions[: max(0, limit)]
