from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

from backend.models import GameState, Piece
from backend.models.schemas import PositionFactorView
from backend.rules import RuleEngine
from backend.rules.terrain import is_scorched
from backend.rules.tuning import ability_parameter, piece_parameter
from backend.rules.variant_system import (
    FINISHED_STATUSES,
    ability_cooldown_remaining,
    affinity_start_squares,
    objective_center_squares,
    piece_runtime_active,
    uses_royal_safety,
)

from .weights import (
    BASE_FACTOR_WEIGHTS,
    CLASSIC_INTRINSIC_VALUES,
    FACTOR_ORDER,
    MODEL_VERSION,
    VICTORY_WEIGHT_OVERRIDES,
)

COLORS = ("white", "black")


@dataclass(frozen=True)
class EvaluationResult:
    score: float
    factors: tuple[PositionFactorView, ...]
    values: dict[str, dict[str, float]]


def opposing(color: str) -> str:
    return "black" if color == "white" else "white"


def chass_position_hash(state: GameState) -> str:
    payload = state.model_dump(
        mode="json",
        exclude={"id", "rematch"},
    )
    encoded = json.dumps(
        {"model": MODEL_VERSION, "state": payload},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _advantage(white: float, black: float, tolerance: float = 0.02) -> str:
    if white > black + tolerance:
        return "white"
    if black > white + tolerance:
        return "black"
    return "balanced"


def _number(value: float) -> int | float:
    rounded = round(value, 1)
    return int(rounded) if float(rounded).is_integer() else rounded


def _lead_summary(label: str, white: float, black: float, unit: str = "") -> str:
    difference = abs(white - black)
    if difference < 0.05:
        return f"{label} is balanced."
    leader = "White" if white > black else "Black"
    suffix = f" {unit}" if unit else ""
    return f"{leader} leads by {_number(difference)}{suffix}."


def _safe_piece_parameter(
    state: GameState,
    piece_type: str,
    parameter_id: str,
    fallback: int,
) -> int:
    try:
        return piece_parameter(state, piece_type, parameter_id)
    except KeyError:
        return fallback


def _safe_ability_parameter(
    state: GameState,
    ability_id: str,
    parameter_id: str,
    fallback: int,
) -> int:
    try:
        return ability_parameter(state, ability_id, parameter_id)
    except KeyError:
        return fallback


def intrinsic_piece_value(state: GameState, piece: Piece) -> float:
    if piece.type == "barricade" or piece.color == "neutral":
        return 0.0
    if piece.type in CLASSIC_INTRINSIC_VALUES:
        value = CLASSIC_INTRINSIC_VALUES[piece.type]
    elif piece.type == "maharani":
        blockers = _safe_piece_parameter(state, "maharani", "blockersCrossed", 1)
        value = 11.5 + (1.5 * math.sqrt(max(1, blockers)))
    elif piece.type == "catapult":
        movement = _safe_piece_parameter(state, "catapult", "movementDistance", 1)
        short_skip = _safe_piece_parameter(state, "catapult", "shortProjectileSkip", 1)
        short_recovery = _safe_piece_parameter(
            state,
            "catapult",
            "shortRecoveryTurns",
            2,
        )
        long_skip = _safe_piece_parameter(state, "catapult", "longProjectileSkip", 2)
        long_recovery = _safe_piece_parameter(
            state,
            "catapult",
            "longRecoveryTurns",
            4,
        )
        board_span = max(1, max(state.board.rows, state.board.cols) - 1)
        projectile = (
            (1 + (short_skip / board_span)) / (1 + (short_recovery / 3))
            + (1 + (long_skip / board_span)) / (1 + (long_recovery / 3))
        )
        value = 2.8 + (0.55 * movement) + projectile
    elif piece.type == "hypnotizer":
        movement = _safe_piece_parameter(state, "hypnotizer", "movementDistance", 2)
        thresholds = [
            _safe_piece_parameter(state, "hypnotizer", "weakContactTurns", 3),
            _safe_piece_parameter(state, "hypnotizer", "mediumContactTurns", 4),
            _safe_piece_parameter(state, "hypnotizer", "strongContactTurns", 5),
        ]
        conversion_rate = sum(1 / max(1, threshold) for threshold in thresholds)
        value = 2.0 + (0.45 * movement) + (5.5 * conversion_rate)
    elif piece.type == "diplomat":
        movement = _safe_piece_parameter(state, "diplomat", "movementDistance", 1)
        contact = _safe_piece_parameter(state, "diplomat", "contactTurns", 2)
        duration = _safe_piece_parameter(state, "diplomat", "pacifiedTurns", 5)
        retirement = _safe_piece_parameter(
            state,
            "diplomat",
            "retireAfterPacifications",
            5,
        )
        value = (
            1.2
            + (0.45 * movement)
            + (0.55 * duration / max(1, contact))
            + (0.12 * retirement)
            + 0.8
        )
    elif piece.type == "cannibal":
        movement = _safe_piece_parameter(state, "cannibal", "movementDistance", 1)
        consume = _safe_piece_parameter(state, "cannibal", "consumeDistance", 1)
        borrowed = _safe_piece_parameter(
            state,
            "cannibal",
            "borrowedMovementMoves",
            5,
        )
        value = 2.4 + (0.5 * movement) + (0.8 * consume) + (0.35 * borrowed)
    elif piece.type == "elephant":
        movement = _safe_piece_parameter(state, "elephant", "movementDistance", 4)
        charge = _safe_piece_parameter(state, "elephant", "chargeDistance", 2)
        allied = _safe_piece_parameter(state, "elephant", "alliedChargeLimit", 1)
        value = 2.0 + (0.6 * movement) + charge + (0.15 * allied) + 0.5
    else:
        definition = state.piece_definitions.get(piece.type)
        if definition is None:
            value = 1.0
        else:
            repeat_patterns = sum(pattern.repeat for pattern in definition.patterns)
            value = max(1.0, (0.4 * len(definition.patterns)) + repeat_patterns)

    if piece.type == "catapult" and piece_runtime_active(
        state,
        piece,
        "catapult_ready_turn",
    ):
        ready_turn = int(piece.runtime.get("catapult_ready_turn", 0))
        remaining = max(1, ready_turn - state.turn_counts.get(piece.color, 0))
        value *= max(0.5, 1 - (0.08 * remaining))
    if piece_runtime_active(state, piece, "pacified_until_turn"):
        value *= 0.68
    if piece.type == "cannibal" and int(
        piece.runtime.get("cannibal_moves_remaining", 0)
    ) > 0:
        inherited = str(piece.runtime.get("cannibal_form", "queen"))
        if inherited == "cannibal":
            inherited = "queen"
        proxy = piece.model_copy(update={"type": inherited, "runtime": {}})
        inherited_value = intrinsic_piece_value(state, proxy)
        value = max(value, inherited_value * 0.9)
    return max(0.0, value)


def _pieces(state: GameState) -> list[tuple[int, int, Piece]]:
    return [
        (row, col, piece)
        for row, board_row in enumerate(state.board.grid)
        for col, piece in enumerate(board_row)
        if piece is not None
    ]


def _attack_and_activity_maps(
    state: GameState,
    engine: RuleEngine,
    pieces: list[tuple[int, int, Piece]],
) -> tuple[
    dict[str, set[tuple[int, int]]],
    dict[str, float],
    dict[str, list[Any]],
    dict[str, float],
]:
    attacks = {color: set() for color in COLORS}
    activity = {color: 0.0 for color in COLORS}
    moves = {color: [] for color in COLORS}
    activity_by_piece: dict[str, float] = {}
    for row, col, piece in pieces:
        if piece.color not in COLORS:
            continue
        piece_attacks = engine.generate_piece_attacks(state, row, col)
        piece_moves = engine.generate_piece_moves(state, row, col)
        attacks[piece.color].update(piece_attacks)
        moves[piece.color].extend(piece_moves)
        activity_by_piece[piece.piece_id] = float(len(piece_moves))
        activity[piece.color] += len(piece_moves) + (0.35 * len(piece_attacks))
    return attacks, activity, moves, activity_by_piece


def _material_values(
    state: GameState,
    pieces: list[tuple[int, int, Piece]],
) -> dict[str, float]:
    return {
        color: sum(
            intrinsic_piece_value(state, piece)
            for _, _, piece in pieces
            if piece.color == color
        )
        for color in COLORS
    }


def _king_safety_values(
    state: GameState,
    engine: RuleEngine,
    pieces: list[tuple[int, int, Piece]],
    attacks: dict[str, set[tuple[int, int]]],
) -> dict[str, float]:
    positions = {
        color: next(
            (
                (row, col, piece)
                for row, col, piece in pieces
                if piece.color == color and piece.type == "king"
            ),
            None,
        )
        for color in COLORS
    }
    values: dict[str, float] = {}
    for color in COLORS:
        position = positions[color]
        if position is None:
            values[color] = -20.0
            continue
        row, col, king = position
        zone = {
            (row + dr, col + dc)
            for dr in (-1, 0, 1)
            for dc in (-1, 0, 1)
            if 0 <= row + dr < state.board.rows
            and 0 <= col + dc < state.board.cols
        }
        enemy_attacks = attacks[opposing(color)]
        pressure = len(zone & enemy_attacks)
        friendly_shield = sum(
            state.board.grid[zone_row][zone_col] is not None
            and state.board.grid[zone_row][zone_col].color == color
            for zone_row, zone_col in zone
            if (zone_row, zone_col) != (row, col)
        )
        escapes = sum(
            option.to_row >= 0
            and (option.to_row, option.to_col) not in enemy_attacks
            for option in engine.generate_piece_moves(state, row, col)
        )
        checked = engine.is_king_in_check(state, color)
        immune = piece_runtime_active(state, king, "capture_immune_until_turn")
        values[color] = (
            6.0
            + (0.35 * friendly_shield)
            + (0.4 * escapes)
            - (1.05 * pressure)
            - (2.8 if checked else 0)
            + (1.0 if immune else 0)
        )
    return values


def _capture_swing(state: GameState, color: str, option: Any) -> float:
    total = 0.0
    score_sensitive = state.configuration.victory.mode in {
        "point_race",
        "royal_score",
    } or any(
        setting.id == "score_target_win" and setting.enabled
        for setting in state.rules
    )
    for capture in option.captures:
        value = intrinsic_piece_value(state, capture.piece)
        if score_sensitive and capture.piece.color != color:
            # Configured points are capture rewards, not a proxy for mobility.
            value += 0.6 * max(0, capture.piece.points or 0)
        total += value if capture.piece.color != color else -value
    return total


def _double_capture_pressure(
    state: GameState,
    color: str,
    pieces: list[tuple[int, int, Piece]],
) -> float:
    setting = next(
        (
            rule
            for rule in state.rules
            if rule.id == "double_capture_rook" and rule.enabled
        ),
        None,
    )
    if setting is None:
        return 0.0
    capture_count = max(2, int(setting.params.get("captureCount", 2)))
    pressure = 0.0
    for row, col, piece in pieces:
        if piece.color != color or piece.type != "rook":
            continue
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            enemies = 0
            target_row, target_col = row + dr, col + dc
            while 0 <= target_row < state.board.rows and 0 <= target_col < state.board.cols:
                target = state.board.grid[target_row][target_col]
                if target is not None:
                    if target.type == "barricade" or target.color == color:
                        break
                    enemies += 1
                    if enemies >= capture_count:
                        pressure += 2.5
                        break
                target_row += dr
                target_col += dc
    return pressure


def _tactical_values(
    state: GameState,
    engine: RuleEngine,
    pieces: list[tuple[int, int, Piece]],
    attacks: dict[str, set[tuple[int, int]]],
    moves: dict[str, list[Any]],
) -> dict[str, float]:
    defended = attacks
    values: dict[str, float] = {}
    for color in COLORS:
        swings = [_capture_swing(state, color, option) for option in moves[color]]
        positive_swings = [swing for swing in swings if swing > 0]
        hanging = 0.0
        enemy = opposing(color)
        for row, col, piece in pieces:
            if piece.color != enemy or (row, col) not in attacks[color]:
                continue
            value = intrinsic_piece_value(state, piece)
            hanging += value * (0.18 if (row, col) in defended[enemy] else 0.35)
        checked = engine.is_king_in_check(state, enemy)
        values[color] = (
            (max(positive_swings, default=0.0) * 0.9)
            + (sum(positive_swings) * 0.08)
            + hanging
            + (2.5 if checked else 0)
            + _double_capture_pressure(state, color, pieces)
        )
    return values


def _center_values(
    state: GameState,
    attacks: dict[str, set[tuple[int, int]]],
) -> dict[str, float]:
    general_center = set(objective_center_squares(state.board.rows, state.board.cols))
    affinity = affinity_start_squares(state.board.rows, state.board.cols)
    values = {color: 0.0 for color in COLORS}
    for color in COLORS:
        targets = (
            set(affinity[color])
            if state.configuration.victory.mode == "center_dominion"
            or state.configuration.custom_rules.affinity_enabled
            else general_center
        )
        occupied = sum(
            (piece := state.board.grid[row][col]) is not None and piece.color == color
            for row, col in targets
        )
        influenced = len(attacks[color] & targets)
        values[color] = (2.0 * occupied) + (0.65 * influenced)
    return values


def _pawn_structure(
    state: GameState,
    color: str,
    pieces: list[tuple[int, int, Piece]],
) -> tuple[float, dict[str, float]]:
    pawns = [
        (row, col)
        for row, col, piece in pieces
        if piece.color == color and piece.type == "pawn"
    ]
    enemy_pawns = [
        (row, col)
        for row, col, piece in pieces
        if piece.color == opposing(color) and piece.type == "pawn"
    ]
    files = {col for _, col in pawns}
    doubled = sum(
        max(0, sum(pawn_col == col for _, pawn_col in pawns) - 1)
        for col in files
    )
    isolated = sum(not ({col - 1, col + 1} & files) for _, col in pawns)
    passed = 0
    advancement = 0.0
    travel = max(1, state.board.rows - 2)
    for row, col in pawns:
        enemy_ahead = any(
            enemy_col in {col - 1, col, col + 1}
            and (enemy_row < row if color == "white" else enemy_row > row)
            for enemy_row, enemy_col in enemy_pawns
        )
        passed += not enemy_ahead
        advancement += (
            (state.board.rows - 2 - row) / travel
            if color == "white"
            else (row - 1) / travel
        )
    score = (1.2 * passed) - (0.45 * isolated) - (0.55 * doubled) + (0.3 * advancement)
    return score, {
        "passed": float(passed),
        "isolated": float(isolated),
        "doubled": float(doubled),
        "advancement": advancement,
    }


def _piece_positions_by_color(
    pieces: list[tuple[int, int, Piece]],
) -> dict[str, list[tuple[int, int, Piece]]]:
    return {
        color: [item for item in pieces if item[2].color == color]
        for color in COLORS
    }


def _ability_readiness(state: GameState, color: str, ability_id: str) -> float:
    remaining = ability_cooldown_remaining(state, color, ability_id)
    return 1 / (1 + remaining)


def _home_space_count(state: GameState, color: str) -> int:
    count = (
        state.gambit.config.setup_rows
        if state.gambit is not None
        else min(2, state.board.rows)
    )
    rows = (
        range(state.board.rows - count, state.board.rows)
        if color == "white"
        else range(count)
    )
    return sum(
        state.board.grid[row][col] is None and not is_scorched(state, row, col)
        for row in rows
        for col in range(state.board.cols)
    )


def _necromancy_value(state: GameState, color: str) -> float:
    cooldown = _safe_ability_parameter(state, "necromancy", "cooldownTurns", 9)
    readiness = _ability_readiness(state, color, "necromancy")
    revived = set(state.abilities.runtime[color].get("revived_piece_ids", []))
    affordable = [
        intrinsic_piece_value(state, piece)
        for piece in state.captured_pieces.get(color, [])
        if piece.piece_id not in revived
        and piece.type not in {"king", "barricade", "cannibal"}
        and (piece.points or 0) <= state.score[color]
    ]
    if not affordable or _home_space_count(state, color) == 0:
        return 0.0
    cycle = 1 / (1 + (cooldown / 6))
    return readiness * cycle * (
        (0.65 * max(affordable)) + (0.35 * math.log1p(len(affordable)))
    )


def _getaway_value(
    state: GameState,
    color: str,
    color_pieces: list[tuple[int, int, Piece]],
) -> float:
    if not uses_royal_safety(state):
        return 0.0
    limit = _safe_ability_parameter(state, "getaway", "usesPerGame", 1)
    used = int(state.abilities.usage_count[color].get("getaway", 0))
    remaining = max(0, limit - used)
    queens = sum(piece.type == "queen" for _, _, piece in color_pieces)
    if not remaining or not queens:
        return 0.0
    return 1.4 * min(2, queens) * math.log1p(remaining)


def _eye_value(
    state: GameState,
    color: str,
    positions: dict[str, list[tuple[int, int, Piece]]],
    activity_by_piece: dict[str, float],
) -> float:
    cooldown = _safe_ability_parameter(state, "eye_for_an_eye", "cooldownTurns", 10)
    readiness = _ability_readiness(state, color, "eye_for_an_eye")
    own_types = {piece.type for _, _, piece in positions[color]}
    enemy_types = {piece.type for _, _, piece in positions[opposing(color)]}
    eligible = own_types & enemy_types - {"king", "barricade", "diplomat"}
    best = 0.0
    for piece_type in eligible:
        own = [piece for _, _, piece in positions[color] if piece.type == piece_type]
        enemy = [
            piece
            for _, _, piece in positions[opposing(color)]
            if piece.type == piece_type
        ]
        for own_piece in own:
            for enemy_piece in enemy:
                positional_delta = activity_by_piece.get(
                    enemy_piece.piece_id,
                    0.0,
                ) - activity_by_piece.get(own_piece.piece_id, 0.0)
                best = max(best, 0.6 + (0.18 * positional_delta))
    return max(0.0, best) * readiness / (1 + (cooldown / 8))


def _kamikaze_value(
    state: GameState,
    color: str,
    color_pieces: list[tuple[int, int, Piece]],
) -> float:
    radius = _safe_ability_parameter(state, "kamikaze", "blastRadius", 2)
    travel = max(1, state.board.rows - 2)
    value = 0.0
    for row, _, piece in color_pieces:
        if piece.type != "pawn":
            continue
        progress = (
            (state.board.rows - 2 - row) / travel
            if color == "white"
            else (row - 1) / travel
        )
        radius_factor = radius / max(1, state.board.cols)
        value += 0.15 * (1 + radius_factor) + (max(0.0, progress) ** 2) * (
            1.2 + radius_factor
        )
    return value


def _episcopal_value(
    state: GameState,
    color: str,
    color_pieces: list[tuple[int, int, Piece]],
) -> float:
    bishops = sum(piece.type == "bishop" for _, _, piece in color_pieces)
    if not bishops:
        return 0.0
    cooldown = _safe_ability_parameter(state, "episcopal", "cooldownTurns", 6)
    shift = _safe_ability_parameter(state, "episcopal", "shiftDistance", 1)
    readiness = _ability_readiness(state, color, "episcopal")
    range_factor = shift / max(1, max(state.board.rows, state.board.cols) - 1)
    return bishops * readiness * (1 + (2.5 * range_factor)) / (1 + (cooldown / 8))


def _power_of_love_value(
    state: GameState,
    color: str,
    color_pieces: list[tuple[int, int, Piece]],
) -> float:
    duration = _safe_ability_parameter(state, "power_of_love", "durationTurns", 10)
    queens = sum(piece.type == "queen" for _, _, piece in color_pieces)
    king = next((piece for _, _, piece in color_pieces if piece.type == "king"), None)
    active = 0
    if king is not None:
        active = max(
            0,
            int(king.runtime.get("love_until_turn", 0)) - state.turn_counts[color],
        )
    latent = queens * (0.35 + (0.25 * duration / (duration + 5)))
    return latent + (3.2 * active / max(1, duration))


def _scorch_value(state: GameState, color: str) -> float:
    cooldown = _safe_ability_parameter(state, "scorch", "cooldownTurns", 10)
    limit = _safe_ability_parameter(state, "scorch", "usesPerGame", 2)
    minimum_gap = _safe_ability_parameter(state, "scorch", "minimumGap", 1)
    used = int(state.abilities.usage_count[color].get("scorch", 0))
    remaining_uses = max(0, limit - used)
    if not remaining_uses:
        return 0.0
    readiness = _ability_readiness(state, color, "scorch")
    open_squares = sum(
        state.board.grid[row][col] is None and not is_scorched(state, row, col)
        for row in range(state.board.rows)
        for col in range(state.board.cols)
    )
    availability = open_squares / max(1, state.board.rows * state.board.cols)
    spacing_penalty = 1 / (1 + (0.2 * minimum_gap))
    return (
        math.log1p(remaining_uses)
        * readiness
        * availability
        * spacing_penalty
        / (1 + (cooldown / 10))
        * 2.2
    )


def _custom_runtime_value(
    state: GameState,
    color: str,
    color_pieces: list[tuple[int, int, Piece]],
) -> float:
    value = 0.0
    for _, _, piece in color_pieces:
        if piece.type == "catapult":
            ready_turn = int(piece.runtime.get("catapult_ready_turn", 0))
            remaining = max(0, ready_turn - state.turn_counts[color])
            value += 0.45 / (1 + remaining)
        elif piece.type == "hypnotizer":
            progress = int(piece.runtime.get("recruit_progress", 0))
            threshold = int(piece.runtime.get("recruit_threshold", 0))
            if progress > 0 and threshold > 0:
                target = next(
                    (
                        target
                        for row in state.board.grid
                        for target in row
                        if target is not None
                        and target.piece_id == piece.runtime.get("recruit_target_id")
                    ),
                    None,
                )
                target_value = intrinsic_piece_value(state, target) if target else 3.0
                value += 2 * target_value * min(1.0, progress / threshold)
        elif piece.type == "diplomat":
            contact_turns = _safe_piece_parameter(
                state,
                "diplomat",
                "contactTurns",
                2,
            )
            contacts = piece.runtime.get("diplomat_contacts", {})
            value += sum(
                min(1.0, int(progress) / max(1, contact_turns))
                for progress in contacts.values()
            )
            retirement = _safe_piece_parameter(
                state,
                "diplomat",
                "retireAfterPacifications",
                5,
            )
            value += 0.2 * max(
                0,
                retirement - int(piece.runtime.get("pacifications", 0)),
            )
        elif piece.type == "cannibal":
            remaining = int(piece.runtime.get("cannibal_moves_remaining", 0))
            configured = _safe_piece_parameter(
                state,
                "cannibal",
                "borrowedMovementMoves",
                5,
            )
            value += 1.5 * min(1.0, remaining / max(1, configured))
    return value


def _affinity_resource_value(state: GameState, color: str, engine: RuleEngine) -> float:
    if not state.configuration.custom_rules.affinity_enabled:
        return 0.0
    config = state.configuration.custom_rules
    points = state.affinity.command_points[color]
    cap = max(1, config.command_point_cap)
    controls = engine.gambit.affinity.controls(state, color)
    primed = state.affinity.primed[color]
    remaining_power = sum(
        max(0, config.power_usage_caps[power] - state.affinity.power_usage[color].get(power, 0))
        / max(1, cost)
        for power, cost in config.power_costs.items()
    )
    return (
        (1.2 * points)
        + (0.7 * points / cap)
        + (1.0 if controls else 0)
        + (0.45 if primed else 0)
        + (0.2 * remaining_power)
        + (0.08 * math.log1p(cap))
    )


def _special_resource_values(
    state: GameState,
    engine: RuleEngine,
    positions: dict[str, list[tuple[int, int, Piece]]],
    activity_by_piece: dict[str, float],
) -> dict[str, float]:
    values = {color: 0.0 for color in COLORS}
    for color in COLORS:
        values[color] += _custom_runtime_value(state, color, positions[color])
        values[color] += _affinity_resource_value(state, color, engine)
        selected = set(state.abilities.selected.get(color, []))
        for ability_id in selected:
            if ability_id == "necromancy":
                values[color] += _necromancy_value(state, color)
            elif ability_id == "getaway":
                values[color] += _getaway_value(state, color, positions[color])
            elif ability_id == "eye_for_an_eye":
                values[color] += _eye_value(
                    state,
                    color,
                    positions,
                    activity_by_piece,
                )
            elif ability_id == "kamikaze":
                values[color] += _kamikaze_value(state, color, positions[color])
            elif ability_id == "episcopal":
                values[color] += _episcopal_value(state, color, positions[color])
            elif ability_id == "power_of_love":
                values[color] += _power_of_love_value(state, color, positions[color])
            elif ability_id == "scorch":
                values[color] += _scorch_value(state, color)
    return values


def _history_capture_count(state: GameState, color: str) -> int:
    return sum(
        capture.piece.color == color and capture.piece.type != "diplomat"
        for record in state.history
        for capture in record.captures
    )


def _goal_values(
    state: GameState,
    engine: RuleEngine,
    pieces: list[tuple[int, int, Piece]],
    center_values: dict[str, float],
) -> dict[str, float]:
    mode = state.configuration.victory.mode
    values = {color: 0.0 for color in COLORS}
    if mode == "point_race":
        target = max(1, state.configuration.victory.target_points)
        for color in COLORS:
            progress = min(0.999, state.score[color] / target)
            values[color] = 10 * (progress**1.6)
    elif mode == "royal_score":
        scale = max(1, max(state.score.values(), default=0), state.configuration.victory.target_points)
        for color in COLORS:
            values[color] = 7 * state.score[color] / scale
    elif mode == "elimination":
        current = {
            color: sum(
                piece.color == color and piece.type != "diplomat"
                for _, _, piece in pieces
            )
            for color in COLORS
        }
        initial = {
            color: current[color] + _history_capture_count(state, color)
            for color in COLORS
        }
        for color in COLORS:
            enemy = opposing(color)
            values[color] = 10 * (
                1 - (current[enemy] / max(1, initial[enemy]))
            )
    elif mode == "center_dominion":
        target = max(1, state.configuration.victory.dominion_rounds)
        for color in COLORS:
            progress = state.center_dominion.progress[color] / target
            values[color] = (
                8 * progress
                + (1.4 if state.center_dominion.primed[color] else 0)
                + (0.35 * center_values[color])
            )
    elif mode == "royal_center":
        targets = objective_center_squares(state.board.rows, state.board.cols)
        max_distance = max(1, state.board.rows + state.board.cols - 2)
        for color in COLORS:
            king = engine.find_king(state, color)
            if king is None:
                values[color] = 0.0
                continue
            distance = min(
                abs(king[0] - row) + abs(king[1] - col)
                for row, col in targets
            )
            values[color] = 10 * (1 - (distance / max_distance))
    elif mode == "check_race":
        target = max(1, state.configuration.victory.check_target)
        for color in COLORS:
            values[color] = 10 * min(0.999, state.check_race.checks[color] / target)
    elif mode == "timed" and state.clock is not None:
        for color in COLORS:
            remaining = state.clock.remaining_seconds[color]
            initial = max(1, state.clock.initial_seconds)
            values[color] = 8 * max(0.0, min(1.0, remaining / initial))
    else:
        for color in COLORS:
            enemy = opposing(color)
            if engine.find_king(state, enemy) is None:
                values[color] = 10.0
            elif engine.is_king_in_check(state, enemy):
                values[color] = 1.5

    score_target = next(
        (
            setting
            for setting in state.rules
            if setting.id == "score_target_win" and setting.enabled
        ),
        None,
    )
    if score_target is not None:
        target = max(1, int(score_target.params.get("targetScore", 21)))
        for color in COLORS:
            values[color] += 6 * min(0.999, state.score[color] / target)
    return values


def _terrain_values(
    state: GameState,
    pieces: list[tuple[int, int, Piece]],
    engine: RuleEngine,
) -> dict[str, float]:
    values = {color: 0.0 for color in COLORS}
    kings = {color: engine.find_king(state, color) for color in COLORS}
    control_range = _safe_piece_parameter(state, "barricade", "controlRange", 1)
    movement = _safe_piece_parameter(state, "barricade", "movementDistance", 1)
    for row, col, piece in pieces:
        if piece.type != "barricade":
            continue
        for color in COLORS:
            controlled = any(
                candidate.color == color
                and max(abs(source_row - row), abs(source_col - col)) <= control_range
                for source_row, source_col, candidate in pieces
            )
            if controlled:
                values[color] += 0.7 + (0.08 * movement)
            king = kings[color]
            if king is not None and max(abs(king[0] - row), abs(king[1] - col)) <= 2:
                values[color] += 0.35
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                target_row, target_col = row + dr, col + dc
                while (
                    0 <= target_row < state.board.rows
                    and 0 <= target_col < state.board.cols
                ):
                    target = state.board.grid[target_row][target_col]
                    if target is not None:
                        if target.type == "rook" and target.color == color:
                            values[color] += 0.5
                        break
                    if is_scorched(state, target_row, target_col):
                        break
                    target_row += dr
                    target_col += dc
    for terrain in state.terrain:
        if terrain.kind != "scorched" or terrain.owner not in COLORS:
            continue
        owner = terrain.owner
        values[owner] += 0.25
        enemy_king = kings[opposing(owner)]
        if enemy_king is not None:
            distance = max(
                abs(enemy_king[0] - terrain.row),
                abs(enemy_king[1] - terrain.col),
            )
            values[owner] += 0.6 / (1 + distance)
    return values


def _factor_weights(state: GameState) -> dict[str, float]:
    weights = dict(BASE_FACTOR_WEIGHTS)
    weights.update(VICTORY_WEIGHT_OVERRIDES[state.configuration.victory.mode])
    if not uses_royal_safety(state) and state.configuration.victory.mode != "king_capture":
        weights["king_safety"] *= 0.3
    return weights


def _factor_difference(white: float, black: float, stability: float = 1.0) -> float:
    return (white - black) / (abs(white) + abs(black) + stability)


def _factor(
    factor_id: str,
    label: str,
    values: dict[str, float],
    summary: str,
    tolerance: float = 0.05,
) -> PositionFactorView:
    return PositionFactorView(
        id=factor_id,
        label=label,
        whiteValue=round(values["white"], 2),
        blackValue=round(values["black"], 2),
        advantage=_advantage(values["white"], values["black"], tolerance),
        summary=summary,
    )


class ChassEvaluator:
    def __init__(self, engine: RuleEngine) -> None:
        self.engine = engine

    def evaluate(self, state: GameState, *, detailed: bool = True) -> EvaluationResult:
        if state.winner == "white":
            return EvaluationResult(score=100.0, factors=(), values={})
        if state.winner == "black":
            return EvaluationResult(score=-100.0, factors=(), values={})
        if state.phase == "finished" or state.game_status in FINISHED_STATUSES:
            return EvaluationResult(score=0.0, factors=(), values={})

        pieces = _pieces(state)
        positions = _piece_positions_by_color(pieces)
        attacks, activity, moves, activity_by_piece = _attack_and_activity_maps(
            state,
            self.engine,
            pieces,
        )
        material = _material_values(state, pieces)
        safety = _king_safety_values(state, self.engine, pieces, attacks)
        tactics = _tactical_values(
            state,
            self.engine,
            pieces,
            attacks,
            moves,
        )
        center = _center_values(state, attacks)
        pawn_results = {
            color: _pawn_structure(state, color, pieces) for color in COLORS
        }
        pawn_values = {color: pawn_results[color][0] for color in COLORS}
        resources = _special_resource_values(
            state,
            self.engine,
            positions,
            activity_by_piece,
        )
        terrain = _terrain_values(state, pieces, self.engine)
        goal = _goal_values(state, self.engine, pieces, center)
        tempo = {
            "white": 1.0 if state.current_player == "white" else 0.0,
            "black": 1.0 if state.current_player == "black" else 0.0,
        }

        values = {
            "goal_progress": goal,
            "material": material,
            "king_safety": safety,
            "tactical_pressure": tactics,
            "piece_activity": activity,
            "center_control": center,
            "special_resources": resources,
            "pawn_structure": pawn_values,
            "terrain": terrain,
            "tempo": tempo,
        }
        weights = _factor_weights(state)
        active_factors = set(FACTOR_ORDER)
        if not any(piece.type == "pawn" for _, _, piece in pieces):
            active_factors.discard("pawn_structure")
        if not (
            state.configuration.special_abilities.enabled
            or state.configuration.custom_rules.affinity_enabled
            or any(piece.is_custom for _, _, piece in pieces)
            or any(state.score.values())
            or state.clock is not None
        ):
            active_factors.discard("special_resources")
        if not state.terrain and not any(
            piece.type == "barricade" for _, _, piece in pieces
        ):
            active_factors.discard("terrain")

        weighted = 0.0
        total_weight = 0.0
        for factor_id in FACTOR_ORDER:
            if factor_id not in active_factors:
                continue
            weight = weights[factor_id]
            stability = 0.5 if factor_id in {"tempo", "goal_progress"} else 1.0
            weighted += weight * _factor_difference(
                values[factor_id]["white"],
                values[factor_id]["black"],
                stability,
            )
            total_weight += weight
        score = 10 * weighted / max(0.001, total_weight)

        if not detailed:
            return EvaluationResult(score=score, factors=(), values=values)

        pawn_details = {color: pawn_results[color][1] for color in COLORS}
        factors = [
            _factor(
                "goal_progress",
                "Win Condition",
                goal,
                _lead_summary("Win-condition progress", goal["white"], goal["black"]),
            ),
            _factor(
                "material",
                "Material Utility",
                material,
                _lead_summary(
                    "Behavior-based material",
                    material["white"],
                    material["black"],
                    "utility",
                ),
            ),
            _factor(
                "king_safety",
                "King Safety",
                safety,
                _lead_summary("King safety", safety["white"], safety["black"]),
            ),
            _factor(
                "tactical_pressure",
                "Tactical Pressure",
                tactics,
                _lead_summary("Tactical pressure", tactics["white"], tactics["black"]),
            ),
            _factor(
                "piece_activity",
                "Piece Activity",
                activity,
                _lead_summary("Board activity", activity["white"], activity["black"]),
            ),
            _factor(
                "center_control",
                "Center Control",
                center,
                _lead_summary("Center influence", center["white"], center["black"]),
            ),
            _factor(
                "special_resources",
                "Special Resources",
                resources,
                _lead_summary("Special-resource utility", resources["white"], resources["black"]),
            ),
            _factor(
                "pawn_structure",
                "Pawn Structure",
                pawn_values,
                (
                    "White: "
                    f"{int(pawn_details['white']['passed'])} passed, "
                    f"{int(pawn_details['white']['isolated'])} isolated, "
                    f"{int(pawn_details['white']['doubled'])} doubled. Black: "
                    f"{int(pawn_details['black']['passed'])} passed, "
                    f"{int(pawn_details['black']['isolated'])} isolated, "
                    f"{int(pawn_details['black']['doubled'])} doubled."
                ),
            ),
            _factor(
                "terrain",
                "Terrain Influence",
                terrain,
                _lead_summary("Terrain influence", terrain["white"], terrain["black"]),
            ),
            _factor(
                "tempo",
                "Tempo",
                tempo,
                f"{state.current_player.title()} has the move.",
            ),
        ]
        visible_factors = tuple(
            factor for factor in factors if factor.id in active_factors
        )
        return EvaluationResult(score=score, factors=visible_factors, values=values)
