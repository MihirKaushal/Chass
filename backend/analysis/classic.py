from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from backend.catalog import build_default_piece_definitions, classic_layout
from backend.models import GameState, PieceDefinition
from backend.models.schemas import PositionFactorView
from backend.rules.variant_system import FINISHED_STATUSES

if TYPE_CHECKING:
    from backend.rules import RuleEngine

CLASSIC_TYPES = frozenset({"pawn", "knight", "bishop", "rook", "queen", "king"})
CLASSIC_POINTS: dict[str, int] = {
    "pawn": 1,
    "knight": 3,
    "bishop": 3,
    "rook": 5,
    "queen": 9,
    "king": 0,
}
REQUIRED_CLASSIC_RULES = frozenset({"check", "checkmate", "stalemate"})
DISABLED_CLASSIC_RULES = frozenset({"double_capture_rook", "score_target_win"})
PIECE_TO_FEN = {
    "pawn": "p",
    "knight": "n",
    "bishop": "b",
    "rook": "r",
    "queen": "q",
    "king": "k",
}


@dataclass(frozen=True)
class ClassicAnalysisEligibility:
    eligible: bool
    enabled: bool
    reason: str | None = None


def _layout_signature(layout: list[dict[str, Any]]) -> list[tuple[int, int, str, str]]:
    return sorted(
        (
            int(piece["row"]),
            int(piece["col"]),
            str(piece["type"]),
            str(piece["color"]),
        )
        for piece in layout
        if piece.get("type") != "barricade"
    )


def _definition_signature(definition: PieceDefinition) -> dict[str, Any]:
    payload = definition.model_dump(mode="json")
    if definition.type == "king" and payload.get("points") == 0:
        payload["points"] = None
    return payload


def _definitions_are_classic(state: GameState) -> bool:
    defaults = build_default_piece_definitions()
    for piece_type in CLASSIC_TYPES:
        current = state.piece_definitions.get(piece_type)
        expected = defaults.get(piece_type)
        if current is None or expected is None:
            return False
        if _definition_signature(current) != _definition_signature(expected):
            return False
    return True


def classic_analysis_eligibility(
    state: GameState,
    *,
    require_enabled: bool = True,
) -> ClassicAnalysisEligibility:
    enabled = state.configuration.match_predictor_enabled
    if require_enabled and not enabled:
        return ClassicAnalysisEligibility(
            eligible=False,
            enabled=False,
            reason="Match Predictor was disabled for this game.",
        )

    if state.variant != "classic" or state.gambit is not None:
        return ClassicAnalysisEligibility(False, enabled, "Available only in Classic Chass.")
    if state.board.rows != 8 or state.board.cols != 8:
        return ClassicAnalysisEligibility(False, enabled, "Classic analysis requires an 8x8 board.")

    configuration = state.configuration
    if configuration.preset_id != "classic" or configuration.formation_id != "classic":
        return ClassicAnalysisEligibility(
            False,
            enabled,
            "The starting mode or formation is not untouched Classic Chass.",
        )
    if (
        len(configuration.enabled_piece_types) != len(CLASSIC_TYPES)
        or set(configuration.enabled_piece_types) != CLASSIC_TYPES
    ):
        return ClassicAnalysisEligibility(False, enabled, "Classic pieces were changed.")
    if configuration.piece_parameters and any(configuration.piece_parameters.values()):
        return ClassicAnalysisEligibility(False, enabled, "Classic piece behavior was changed.")
    if not _definitions_are_classic(state):
        return ClassicAnalysisEligibility(False, enabled, "Classic piece definitions or values were changed.")

    expected_layout = _layout_signature(classic_layout(8, 8))
    configured_layout = configuration.initial_layout
    if configured_layout and _layout_signature(configured_layout) != expected_layout:
        return ClassicAnalysisEligibility(False, enabled, "The Classic starting position was changed.")
    if configuration.victory.mode != "checkmate":
        return ClassicAnalysisEligibility(False, enabled, "Classic checkmate victory is required.")
    if configuration.custom_rules.affinity_enabled:
        return ClassicAnalysisEligibility(False, enabled, "Custom rules disable Classic analysis.")
    if configuration.special_abilities.enabled:
        return ClassicAnalysisEligibility(False, enabled, "Special abilities disable Classic analysis.")
    if state.terrain:
        return ClassicAnalysisEligibility(False, enabled, "Custom board terrain disables Classic analysis.")

    rule_settings = {setting.id: setting for setting in state.rules}
    if any(
        rule_id not in rule_settings or not rule_settings[rule_id].enabled
        for rule_id in REQUIRED_CLASSIC_RULES
    ):
        return ClassicAnalysisEligibility(False, enabled, "A required Classic rule was changed.")
    if any(rule_settings.get(rule_id) and rule_settings[rule_id].enabled for rule_id in DISABLED_CLASSIC_RULES):
        return ClassicAnalysisEligibility(False, enabled, "A variant rule is enabled.")
    if any(setting.params for setting in rule_settings.values()):
        return ClassicAnalysisEligibility(False, enabled, "Rule parameters were customized.")

    board_pieces = [piece for row in state.board.grid for piece in row if piece is not None]
    if any(piece.color not in {"white", "black"} or piece.type not in CLASSIC_TYPES for piece in board_pieces):
        return ClassicAnalysisEligibility(False, enabled, "The current board is not a legal Classic position.")
    if any(sum(piece.type == "king" and piece.color == color for piece in board_pieces) != 1 for color in ("white", "black")):
        return ClassicAnalysisEligibility(False, enabled, "Both Classic Kings must remain on the board.")

    return ClassicAnalysisEligibility(True, enabled, None)


def synchronize_match_predictor_setting(state: GameState) -> None:
    if not state.configuration.match_predictor_enabled:
        return
    eligibility = classic_analysis_eligibility(state, require_enabled=False)
    if not eligibility.eligible:
        state.configuration.match_predictor_enabled = False


def _castling_rights(state: GameState) -> str:
    rights: list[str] = []
    for color, row, king_symbol, queen_symbol in (
        ("white", 7, "K", "Q"),
        ("black", 0, "k", "q"),
    ):
        king = state.board.grid[row][4]
        if king is None or king.type != "king" or king.color != color or king.has_moved:
            continue
        kingside_rook = state.board.grid[row][7]
        queenside_rook = state.board.grid[row][0]
        if (
            kingside_rook is not None
            and kingside_rook.type == "rook"
            and kingside_rook.color == color
            and not kingside_rook.has_moved
        ):
            rights.append(king_symbol)
        if (
            queenside_rook is not None
            and queenside_rook.type == "rook"
            and queenside_rook.color == color
            and not queenside_rook.has_moved
        ):
            rights.append(queen_symbol)
    return "".join(rights) or "-"


def _en_passant_square(state: GameState) -> str:
    if not state.history:
        return "-"
    move = state.history[-1]
    if (
        move.action_type != "move"
        or move.piece != "pawn"
        or abs(move.to_row - move.from_row) != 2
    ):
        return "-"
    target_row = (move.from_row + move.to_row) // 2
    return f"{chr(ord('a') + move.to_col)}{state.board.rows - target_row}"


def classic_position_fen(state: GameState) -> str:
    ranks: list[str] = []
    for row in state.board.grid:
        empty = 0
        rank: list[str] = []
        for piece in row:
            if piece is None:
                empty += 1
                continue
            if empty:
                rank.append(str(empty))
                empty = 0
            symbol = PIECE_TO_FEN[piece.type]
            rank.append(symbol.upper() if piece.color == "white" else symbol)
        if empty:
            rank.append(str(empty))
        ranks.append("".join(rank))

    side_to_move = "w" if state.current_player == "white" else "b"
    fullmove_number = (
        (state.history[-1].move_number // 2) + 1
        if state.history
        else 1
    )
    return " ".join(
        (
            "/".join(ranks),
            side_to_move,
            _castling_rights(state),
            _en_passant_square(state),
            str(state.classic.halfmove_clock),
            str(max(1, fullmove_number)),
        )
    )


def classic_position_hash(state: GameState) -> str:
    return hashlib.sha256(classic_position_fen(state).encode("ascii")).hexdigest()


def _advantage(white: float, black: float, tolerance: float = 0.001) -> str:
    if white > black + tolerance:
        return "white"
    if black > white + tolerance:
        return "black"
    return "balanced"


def _lead_summary(label: str, white: float, black: float, unit: str = "") -> str:
    difference = abs(white - black)
    if difference < 0.001:
        return f"{label} is balanced."
    leader = "White" if white > black else "Black"
    rendered = int(difference) if float(difference).is_integer() else round(difference, 1)
    suffix = f" {unit}" if unit else ""
    return f"{leader} leads by {rendered}{suffix}."


def _pawn_structure(state: GameState, color: str) -> dict[str, int]:
    pawns = [
        (row, col)
        for row, board_row in enumerate(state.board.grid)
        for col, piece in enumerate(board_row)
        if piece is not None and piece.type == "pawn" and piece.color == color
    ]
    enemy = "black" if color == "white" else "white"
    enemy_pawns = [
        (row, col)
        for row, board_row in enumerate(state.board.grid)
        for col, piece in enumerate(board_row)
        if piece is not None and piece.type == "pawn" and piece.color == enemy
    ]
    files = {col for _, col in pawns}
    file_counts = {col: sum(pawn_col == col for _, pawn_col in pawns) for col in files}
    doubled = sum(max(0, count - 1) for count in file_counts.values())
    isolated = sum(not ({col - 1, col + 1} & files) for _, col in pawns)
    passed = 0
    for row, col in pawns:
        blocking_files = {col - 1, col, col + 1}
        enemy_ahead = any(
            enemy_col in blocking_files
            and (enemy_row < row if color == "white" else enemy_row > row)
            for enemy_row, enemy_col in enemy_pawns
        )
        if not enemy_ahead:
            passed += 1
    return {"doubled": doubled, "isolated": isolated, "passed": passed}


def _king_safety(
    state: GameState,
    engine: RuleEngine,
    color: str,
    enemy_attacks: set[tuple[int, int]],
) -> float:
    position = engine.find_king(state, color)
    if position is None:
        return -100.0
    row, col = position
    zone = {
        (row + dr, col + dc)
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        if 0 <= row + dr < 8 and 0 <= col + dc < 8
    }
    pressure = len(zone & enemy_attacks)
    forward = -1 if color == "white" else 1
    shield = sum(
        (
            0 <= row + forward < 8
            and 0 <= shield_col < 8
            and (piece := state.board.grid[row + forward][shield_col]) is not None
            and piece.type == "pawn"
            and piece.color == color
        )
        for shield_col in (col - 1, col, col + 1)
    )
    castled = int(col in {2, 6} and state.board.grid[row][col].has_moved)
    return float((shield * 2) + (castled * 2) - (pressure * 1.5))


def extract_position_factors(
    state: GameState,
    engine: RuleEngine,
) -> list[PositionFactorView]:
    material = {
        color: float(
            sum(
                CLASSIC_POINTS[piece.type]
                for row in state.board.grid
                for piece in row
                if piece is not None and piece.color == color
            )
        )
        for color in ("white", "black")
    }

    attacks: dict[str, set[tuple[int, int]]] = {"white": set(), "black": set()}
    for row, board_row in enumerate(state.board.grid):
        for col, piece in enumerate(board_row):
            if piece is not None and piece.color in attacks:
                attacks[piece.color].update(engine.generate_piece_attacks(state, row, col))

    if state.game_status in FINISHED_STATUSES:
        mobility = {"white": 0.0, "black": 0.0}
    else:
        mobility = {
            color: float(len(engine.get_valid_moves_for_color(state, color)))
            for color in ("white", "black")
        }

    safety = {
        "white": _king_safety(state, engine, "white", attacks["black"]),
        "black": _king_safety(state, engine, "black", attacks["white"]),
    }
    pawn_details = {
        color: _pawn_structure(state, color) for color in ("white", "black")
    }
    pawn_scores = {
        color: float(
            (pawn_details[color]["passed"] * 2)
            - pawn_details[color]["isolated"]
            - pawn_details[color]["doubled"]
        )
        for color in ("white", "black")
    }
    center = {(3, 3), (3, 4), (4, 3), (4, 4)}
    center_control = {
        color: float(
            len(attacks[color] & center)
            + sum(
                state.board.grid[row][col] is not None
                and state.board.grid[row][col].color == color
                for row, col in center
            )
        )
        for color in ("white", "black")
    }

    return [
        PositionFactorView(
            id="material",
            label="Material",
            whiteValue=material["white"],
            blackValue=material["black"],
            advantage=_advantage(material["white"], material["black"]),
            summary=_lead_summary("Material", material["white"], material["black"], "points"),
        ),
        PositionFactorView(
            id="king_safety",
            label="King Safety",
            whiteValue=safety["white"],
            blackValue=safety["black"],
            advantage=_advantage(safety["white"], safety["black"], 0.5),
            summary=_lead_summary("King safety", safety["white"], safety["black"]),
        ),
        PositionFactorView(
            id="piece_activity",
            label="Piece Activity",
            whiteValue=mobility["white"],
            blackValue=mobility["black"],
            advantage=_advantage(mobility["white"], mobility["black"], 1),
            summary=_lead_summary("Legal mobility", mobility["white"], mobility["black"], "moves"),
        ),
        PositionFactorView(
            id="pawn_structure",
            label="Pawn Structure",
            whiteValue=pawn_scores["white"],
            blackValue=pawn_scores["black"],
            advantage=_advantage(pawn_scores["white"], pawn_scores["black"], 0.5),
            summary=(
                "White: "
                f"{pawn_details['white']['passed']} passed, "
                f"{pawn_details['white']['isolated']} isolated, "
                f"{pawn_details['white']['doubled']} doubled. Black: "
                f"{pawn_details['black']['passed']} passed, "
                f"{pawn_details['black']['isolated']} isolated, "
                f"{pawn_details['black']['doubled']} doubled."
            ),
        ),
        PositionFactorView(
            id="center_control",
            label="Center Control",
            whiteValue=center_control["white"],
            blackValue=center_control["black"],
            advantage=_advantage(center_control["white"], center_control["black"], 0.5),
            summary=_lead_summary(
                "Center influence",
                center_control["white"],
                center_control["black"],
                "squares",
            ),
        ),
    ]
