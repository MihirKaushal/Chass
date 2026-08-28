from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from backend.analysis.classic import (
    CLASSIC_TYPES,
    DISABLED_CLASSIC_RULES,
    PIECE_TO_FEN,
    REQUIRED_CLASSIC_RULES,
    classic_analysis_eligibility,
    definitions_use_classic_behavior,
)
from backend.catalog import classic_layout
from backend.models import GameState
from backend.rules.variant_system import objective_center_squares

FAIRY_MAX_RANKS = 10
FAIRY_MAX_FILES = 12
FAIRY_VICTORY_MODES = frozenset({"checkmate", "royal_center", "check_race"})


@dataclass(frozen=True)
class CastlingProfile:
    enabled: bool
    king_file: int | None = None
    queenside_rook_file: int | None = None
    kingside_rook_file: int | None = None

    def as_signature(self) -> dict[str, int | bool | None]:
        return {
            "enabled": self.enabled,
            "kingFile": self.king_file,
            "queensideRookFile": self.queenside_rook_file,
            "kingsideRookFile": self.kingside_rook_file,
        }


@dataclass(frozen=True)
class AnalysisProfile:
    engine_id: str
    engine_name: str
    accuracy: str
    calibrated: bool
    profile_id: str
    variant_name: str | None = None
    variant_definition: str | None = None
    castling: CastlingProfile = CastlingProfile(enabled=False)


@dataclass(frozen=True)
class AnalysisProfileSelection:
    enabled: bool
    eligible: bool
    profile: AnalysisProfile | None = None
    reason: str | None = None


STOCKFISH_PROFILE = AnalysisProfile(
    engine_id="stockfish",
    engine_name="Stockfish 18",
    accuracy=(
        "High-strength standard-chess estimate. The untouched Classic opening is shown "
        "with Chass's neutral opening calibration."
    ),
    calibrated=True,
    profile_id="stockfish-standard-8x8-v1",
)

CHASS_PROFILE = AnalysisProfile(
    engine_id="chass",
    engine_name="Chass Engine",
    accuracy=(
        "Experimental handcrafted estimate for fully customized Chass games. "
        "It understands active rules and runtime effects but is not trained or calibrated."
    ),
    calibrated=False,
    profile_id="chass-hce-v1",
)


def _initial_placements(state: GameState) -> list[dict]:
    if state.configuration.initial_layout:
        return [dict(placement) for placement in state.configuration.initial_layout]
    enabled = set(state.configuration.enabled_piece_types)
    return [
        placement
        for placement in classic_layout(state.board.rows, state.board.cols)
        if placement["type"] in enabled
    ]


def _castling_profile(state: GameState) -> tuple[CastlingProfile | None, str | None]:
    placements = _initial_placements(state)
    geometry: dict[str, dict[str, int | None]] = {}
    for color, home_row in (("white", state.board.rows - 1), ("black", 0)):
        kings = [
            piece
            for piece in placements
            if piece.get("type") == "king" and piece.get("color") == color
        ]
        if len(kings) != 1:
            return None, "Both sides must have exactly one King."
        king = kings[0]
        king_row = int(king["row"])
        king_col = int(king["col"])
        rooks = sorted(
            int(piece["col"])
            for piece in placements
            if piece.get("type") == "rook"
            and piece.get("color") == color
            and int(piece["row"]) == king_row
            and abs(int(piece["col"]) - king_col) >= 3
        )
        queenside = max((col for col in rooks if col < king_col), default=None)
        kingside = min((col for col in rooks if col > king_col), default=None)
        if (queenside is not None or kingside is not None) and king_row != home_row:
            return None, "Potential castling Kings must begin on each side's back rank."
        geometry[color] = {
            "king": king_col,
            "queenside": queenside,
            "kingside": kingside,
        }

    if not any(
        geometry[color][side] is not None
        for color in ("white", "black")
        for side in ("queenside", "kingside")
    ):
        return CastlingProfile(enabled=False), None

    king_files = {int(geometry[color]["king"]) for color in ("white", "black")}
    if len(king_files) != 1:
        return None, "Fairy analysis requires matching White and Black castling geometry."
    king_file = king_files.pop()

    resolved: dict[str, int | None] = {}
    for side in ("queenside", "kingside"):
        files = {
            int(geometry[color][side])
            for color in ("white", "black")
            if geometry[color][side] is not None
        }
        if len(files) > 1:
            return None, "Fairy analysis requires matching White and Black castling geometry."
        resolved[side] = next(iter(files), None)

    if king_file - 2 < 0 or king_file + 2 >= state.board.cols:
        return None, "The King needs two board squares on each castling side."
    return (
        CastlingProfile(
            enabled=True,
            king_file=king_file,
            queenside_rook_file=resolved["queenside"],
            kingside_rook_file=resolved["kingside"],
        ),
        None,
    )


def _fairy_reason(state: GameState) -> tuple[str | None, CastlingProfile | None]:
    if state.variant != "classic" or state.gambit is not None:
        return "Hidden or drafted Gambit setup is not a static Fairy variant.", None
    if state.board.rows > FAIRY_MAX_RANKS or state.board.cols > FAIRY_MAX_FILES:
        return "Fairy-Stockfish supports Chass boards up to 10 rows by 12 columns.", None
    if state.configuration.victory.mode not in FAIRY_VICTORY_MODES:
        return (
            "This win condition has stateful Chass logic that Fairy-Stockfish cannot model.",
            None,
        )
    if state.configuration.custom_rules.affinity_enabled:
        return "Affinity Squares and command powers are not static Fairy rules.", None
    if state.configuration.special_abilities.enabled:
        return "Special Abilities are not supported by Fairy-Stockfish.", None
    if state.terrain:
        return "Scorched or custom terrain is not supported by Fairy-Stockfish.", None
    if state.configuration.piece_parameters and any(state.configuration.piece_parameters.values()):
        return "Customized piece movement is not yet supported by Fairy-Stockfish.", None
    if not definitions_use_classic_behavior(state):
        return "Only unchanged standard piece movement is currently supported.", None

    enabled_types = set(state.configuration.enabled_piece_types)
    if not enabled_types or "king" not in enabled_types or not enabled_types <= CLASSIC_TYPES:
        return "Enable only standard chess piece types for Fairy analysis.", None
    positioned_pieces = [
        (row_index, piece)
        for row_index, row in enumerate(state.board.grid)
        for piece in row
        if piece is not None
    ]
    pieces = [piece for _, piece in positioned_pieces]
    if any(
        piece.color not in {"white", "black"} or piece.type not in CLASSIC_TYPES for piece in pieces
    ):
        return "Only standard White and Black pieces can be analyzed.", None
    if any(piece.type not in enabled_types for piece in pieces):
        return "Every starting piece must use an enabled standard piece type.", None
    if any(piece.type == "pawn" for piece in pieces) and not enabled_types.issuperset(
        {"knight", "bishop", "rook", "queen"}
    ):
        return "All standard promotion pieces must remain enabled while Pawns are in play.", None
    if not state.history:
        expected = sorted(
            (
                int(piece["row"]),
                int(piece["col"]),
                str(piece["type"]),
                str(piece["color"]),
            )
            for piece in _initial_placements(state)
        )
        actual = sorted(
            (row, col, piece.type, piece.color)
            for row, board_row in enumerate(state.board.grid)
            for col, piece in enumerate(board_row)
            if piece is not None
        )
        if actual != expected:
            return "The starting board no longer matches its validated configuration.", None
    for color in ("white", "black"):
        if sum(piece.type == "king" and piece.color == color for piece in pieces) != 1:
            return "Both sides must have exactly one King.", None
        pawn_home_row = state.board.rows - 2 if color == "white" else 1
        if any(
            piece.type == "pawn"
            and piece.color == color
            and not piece.has_moved
            and row_index != pawn_home_row
            for row_index, piece in positioned_pieces
        ):
            return "Unmoved Pawns must begin on their home rank for Fairy analysis.", None

    rule_settings = {setting.id: setting for setting in state.rules}
    if any(
        rule_id not in rule_settings or not rule_settings[rule_id].enabled
        for rule_id in REQUIRED_CLASSIC_RULES
    ):
        return "Check, checkmate, and stalemate rules must remain active.", None
    if any(
        rule_settings.get(rule_id) and rule_settings[rule_id].enabled
        for rule_id in DISABLED_CLASSIC_RULES
    ):
        return "Variant capture or score rules are not supported by Fairy-Stockfish.", None
    if any(setting.params for setting in rule_settings.values()):
        return "Raw rule parameters cannot be translated into a verified Fairy profile.", None

    castling, castling_reason = _castling_profile(state)
    if castling_reason:
        return castling_reason, None
    return None, castling


def _square_name(state: GameState, row: int, col: int) -> str:
    return f"{chr(ord('a') + col)}{state.board.rows - row}"


def _generic_start_fen(rows: int, cols: int, victory_mode: str, check_target: int) -> str:
    ranks = [f"{cols - 1}k", *([str(cols)] * (rows - 2)), f"K{cols - 1}"]
    fields = ["/".join(ranks), "w", "-", "-"]
    if victory_mode == "check_race":
        fields.append(f"{check_target}+{check_target}")
    fields.extend(["0", "1"])
    return " ".join(fields)


def _file_name(col: int) -> str:
    return chr(ord("a") + col)


def _compile_fairy_profile(state: GameState, castling: CastlingProfile) -> AnalysisProfile:
    signature = {
        "schema": 2,
        "rows": state.board.rows,
        "cols": state.board.cols,
        "victory": state.configuration.victory.mode,
        "checkTarget": (
            state.configuration.victory.check_target
            if state.configuration.victory.mode == "check_race"
            else None
        ),
        "castling": castling.as_signature(),
    }
    encoded = json.dumps(signature, sort_keys=True, separators=(",", ":")).encode("ascii")
    variant_name = f"chass_{hashlib.sha256(encoded).hexdigest()[:16]}"
    lines = [
        f"[{variant_name}:chess]",
        f"maxRank = {state.board.rows}",
        f"maxFile = {state.board.cols}",
        f"startFen = {_generic_start_fen(state.board.rows, state.board.cols, state.configuration.victory.mode, state.configuration.victory.check_target)}",
        f"promotionRegionWhite = *{state.board.rows}",
        "promotionRegionBlack = *1",
        "doubleStepRegionWhite = *2",
        f"doubleStepRegionBlack = *{state.board.rows - 1}",
    ]
    if castling.enabled:
        assert castling.king_file is not None
        lines.extend(
            [
                "castling = true",
                f"castlingKingFile = {_file_name(castling.king_file)}",
                f"castlingQueensideFile = {_file_name(castling.king_file - 2)}",
                f"castlingKingsideFile = {_file_name(castling.king_file + 2)}",
            ]
        )
        if castling.queenside_rook_file is not None:
            lines.append(f"castlingRookQueensideFile = {_file_name(castling.queenside_rook_file)}")
        if castling.kingside_rook_file is not None:
            lines.append(f"castlingRookKingsideFile = {_file_name(castling.kingside_rook_file)}")
    else:
        lines.append("castling = false")

    if state.configuration.victory.mode == "royal_center":
        targets = " ".join(
            _square_name(state, row, col)
            for row, col in objective_center_squares(state.board.rows, state.board.cols)
        )
        lines.extend(
            [
                "flagPiece = k",
                f"flagRegion = {targets}",
                "flagPieceSafe = true",
                "nMoveRule = 0",
                "nFoldRule = 0",
            ]
        )
    elif state.configuration.victory.mode == "check_race":
        lines.extend(["checkCounting = true", "nMoveRule = 0", "nFoldRule = 0"])

    return AnalysisProfile(
        engine_id="fairy-stockfish",
        engine_name="Fairy-Stockfish",
        accuracy=(
            "Experimental static-variant estimate. Legal moves and terminal behavior are "
            "parity-checked against Chass, but outcome probabilities are not Chass-calibrated."
        ),
        calibrated=False,
        profile_id=variant_name,
        variant_name=variant_name,
        variant_definition="\n".join(lines) + "\n",
        castling=castling,
    )


def select_fairy_profile(state: GameState) -> AnalysisProfileSelection:
    """Compile the deterministic Fairy profile without applying engine preference."""
    fairy_reason, castling = _fairy_reason(state)
    if fairy_reason is not None or castling is None:
        return AnalysisProfileSelection(
            enabled=state.configuration.match_predictor_enabled,
            eligible=False,
            reason=fairy_reason or "This game cannot be represented as a static Fairy variant.",
        )
    return AnalysisProfileSelection(
        enabled=state.configuration.match_predictor_enabled,
        eligible=True,
        profile=_compile_fairy_profile(state, castling),
    )


def select_analysis_profile(
    state: GameState,
    *,
    require_enabled: bool = True,
) -> AnalysisProfileSelection:
    enabled = state.configuration.match_predictor_enabled
    if require_enabled and not enabled:
        return AnalysisProfileSelection(
            enabled=False,
            eligible=False,
            reason="Match Analysis was disabled for this game.",
        )

    stockfish = classic_analysis_eligibility(state, require_enabled=False)
    if stockfish.eligible:
        return AnalysisProfileSelection(enabled=enabled, eligible=True, profile=STOCKFISH_PROFILE)

    fairy = select_fairy_profile(state)
    if fairy.eligible and fairy.profile is not None:
        return fairy
    return AnalysisProfileSelection(
        enabled=enabled,
        eligible=True,
        profile=CHASS_PROFILE,
        reason=(
            "Stockfish and Fairy-Stockfish cannot model every active mechanic, "
            "so Chass Engine will analyze this game."
        ),
    )


def synchronize_match_predictor_setting(state: GameState) -> None:
    # Every valid game now has the native Chass Engine as a fallback. Preserve
    # the player's explicit analysis setting instead of disabling it after edits.
    return


def _castling_rights(state: GameState, profile: AnalysisProfile) -> str:
    castling = profile.castling
    if not castling.enabled or castling.king_file is None:
        return "-"
    rights: list[str] = []
    for color, row, king_side, queen_side in (
        ("white", state.board.rows - 1, "K", "Q"),
        ("black", 0, "k", "q"),
    ):
        king = state.board.grid[row][castling.king_file]
        if king is None or king.type != "king" or king.color != color or king.has_moved:
            continue
        for rook_file, symbol in (
            (castling.kingside_rook_file, king_side),
            (castling.queenside_rook_file, queen_side),
        ):
            if rook_file is None:
                continue
            rook = state.board.grid[row][rook_file]
            if (
                rook is not None
                and rook.type == "rook"
                and rook.color == color
                and not rook.has_moved
            ):
                rights.append(symbol)
    return "".join(rights) or "-"


def _en_passant_square(state: GameState) -> str:
    if not state.history:
        return "-"
    move = state.history[-1]
    if move.action_type != "move" or move.piece != "pawn" or abs(move.to_row - move.from_row) != 2:
        return "-"
    return _square_name(state, (move.from_row + move.to_row) // 2, move.to_col)


def analysis_position_fen(state: GameState, profile: AnalysisProfile) -> str:
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

    fields = [
        "/".join(ranks),
        "w" if state.current_player == "white" else "b",
        _castling_rights(state, profile),
        _en_passant_square(state),
    ]
    if state.configuration.victory.mode == "check_race":
        target = state.configuration.victory.check_target
        fields.append(
            f"{max(0, target - state.check_race.checks['white'])}+"
            f"{max(0, target - state.check_race.checks['black'])}"
        )
    fields.extend(
        [
            str(state.classic.halfmove_clock),
            str(max(1, (len(state.history) // 2) + 1)),
        ]
    )
    return " ".join(fields)


def analysis_position_hash(
    state: GameState,
    profile: AnalysisProfile,
    fen: str | None = None,
) -> str:
    payload = f"{profile.profile_id}\n{fen or analysis_position_fen(state, profile)}"
    return hashlib.sha256(payload.encode("ascii")).hexdigest()
