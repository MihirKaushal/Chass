from __future__ import annotations

import hashlib
import json

from backend.models import CaptureEvent, GameState, Move, MoveOption, Piece
from backend.rules.base import Rule, RuleContext
from backend.rules.variant_system import FINISHED_STATUSES, finish_game, uses_royal_safety

CLASSIC_PIECE_TYPES = frozenset({"pawn", "knight", "bishop", "rook", "queen", "king"})
IRREVERSIBLE_RIGHTS_TYPES = frozenset({"king", "rook"})
POSITION_RIGHTS_TYPES = frozenset({"pawn", "king", "rook"})


def _opposing_color(color: str) -> str:
    return "black" if color == "white" else "white"


def _enabled_rule_ids(state: GameState) -> set[str]:
    return {setting.id for setting in state.rules if setting.enabled}


def _uses_classic_draw_rules(state: GameState) -> bool:
    if state.variant != "classic" or state.configuration.victory.mode not in {
        "checkmate",
        "timed",
    }:
        return False
    if state.configuration.custom_rules.affinity_enabled:
        return False
    if state.configuration.special_abilities.enabled:
        return False
    if _enabled_rule_ids(state) & {"double_capture_rook", "score_target_win"}:
        return False
    return all(
        piece is None or piece.type in CLASSIC_PIECE_TYPES
        for board_row in state.board.grid
        for piece in board_row
    )


def _last_double_pawn_move(state: GameState):
    if not state.history:
        return None
    last_move = state.history[-1]
    if (
        last_move.action_type != "move"
        or last_move.piece != "pawn"
        or abs(last_move.to_row - last_move.from_row) != 2
    ):
        return None
    return last_move


def _en_passant_target(state: GameState, side_to_move: str) -> tuple[int, int] | None:
    last_move = _last_double_pawn_move(state)
    if last_move is None or last_move.player == side_to_move:
        return None
    victim = state.board.grid[last_move.to_row][last_move.to_col]
    if victim is None or victim.type != "pawn" or victim.color == side_to_move:
        return None
    target = ((last_move.from_row + last_move.to_row) // 2, last_move.to_col)
    if state.board.grid[target[0]][target[1]] is not None:
        return None
    if any(
        (pawn := state.board.grid[last_move.to_row][col]) is not None
        and pawn.type == "pawn"
        and pawn.color == side_to_move
        for col in (last_move.to_col - 1, last_move.to_col + 1)
        if 0 <= col < state.board.cols
    ):
        return target
    return None


def _position_key(state: GameState, side_to_move: str) -> str:
    pieces = [
        (
            row,
            col,
            piece.type,
            piece.color,
            piece.has_moved if piece.type in POSITION_RIGHTS_TYPES else False,
        )
        for row, board_row in enumerate(state.board.grid)
        for col, piece in enumerate(board_row)
        if piece is not None
    ]
    payload = {
        "pieces": pieces,
        "side": side_to_move,
        "enPassant": _en_passant_target(state, side_to_move),
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class CastlingRule(Rule):
    id = "castling"
    name = "Castling"
    description = (
        "An unmoved King may move two squares toward an unmoved Rook when the path is "
        "clear and no crossed square is under attack."
    )
    tier = "basic"
    can_disable = False

    @staticmethod
    def _rook_for_direction(
        state: GameState,
        row: int,
        king_col: int,
        direction: int,
        color: str,
    ) -> tuple[int, Piece] | None:
        columns = range(king_col + direction, state.board.cols if direction > 0 else -1, direction)
        for col in columns:
            piece = state.board.grid[row][col]
            if piece is None:
                continue
            if piece.type == "rook" and piece.color == color and not piece.has_moved:
                return col, piece
            return None
        return None

    def generate_moves(
        self,
        state: GameState,
        row: int,
        col: int,
        helper,
        params: dict,
    ) -> list[MoveOption]:
        king = state.board.grid[row][col]
        if (
            king is None
            or king.type != "king"
            or king.color == "neutral"
            or king.has_moved
            or not uses_royal_safety(state)
            or helper.is_king_in_check(state, king.color)
        ):
            return []

        enemy = _opposing_color(king.color)
        options: list[MoveOption] = []
        for direction in (-1, 1):
            rook_entry = self._rook_for_direction(state, row, col, direction, king.color)
            if rook_entry is None:
                continue
            rook_col, _ = rook_entry
            if abs(rook_col - col) < 3:
                continue
            transit_col = col + direction
            destination_col = col + 2 * direction
            if not 0 <= destination_col < state.board.cols:
                continue
            if any(
                helper.is_square_attacked_by_color(state, row, square_col, enemy)
                for square_col in (transit_col, destination_col)
            ):
                continue
            options.append(
                MoveOption(
                    from_row=row,
                    from_col=col,
                    to_row=row,
                    to_col=destination_col,
                    explanation=(
                        "Castle kingside" if direction > 0 else "Castle queenside"
                    ),
                )
            )
        return options

    def apply(
        self,
        state: GameState,
        move: Move,
        context: RuleContext,
        helper,
        params: dict,
    ) -> None:
        king = context.moved_piece
        if (
            king is None
            or context.metadata.get("original_piece_type") != "king"
            or not context.metadata.get("moved_piece_was_unmoved")
            or move.from_row != move.to_row
            or abs(move.to_col - move.from_col) != 2
            or context.target_piece is not None
        ):
            return

        pre_move = state.clone()
        pre_move.board.grid[move.to_row][move.to_col] = context.target_piece
        king_before = king.model_copy(deep=True)
        king_before.has_moved = False
        pre_move.board.grid[move.from_row][move.from_col] = king_before
        if not any(
            option.to_row == move.to_row and option.to_col == move.to_col
            for option in self.generate_moves(
                pre_move,
                move.from_row,
                move.from_col,
                helper,
                params,
            )
        ):
            return

        direction = 1 if move.to_col > move.from_col else -1
        rook_entry = self._rook_for_direction(
            state,
            move.from_row,
            move.to_col,
            direction,
            king.color,
        )
        if rook_entry is None:
            return
        rook_col, rook = rook_entry
        rook_destination = move.from_col + direction
        state.board.grid[move.from_row][rook_col] = None
        rook.has_moved = True
        state.board.grid[move.from_row][rook_destination] = rook
        if not context.simulated:
            context.messages.append(
                "King castled kingside." if direction > 0 else "King castled queenside."
            )


class EnPassantRule(Rule):
    id = "en_passant"
    name = "En Passant"
    description = (
        "A Pawn may capture an adjacent enemy Pawn immediately after that Pawn advances "
        "two squares."
    )
    tier = "basic"
    can_disable = False

    @staticmethod
    def _capture(
        state: GameState,
        row: int,
        col: int,
        target_row: int,
        target_col: int,
        pawn: Piece,
    ) -> tuple[int, int, Piece] | None:
        direction = -1 if pawn.color == "white" else 1
        if target_row != row + direction or abs(target_col - col) != 1:
            return None
        if state.board.grid[target_row][target_col] is not None:
            return None
        last_move = _last_double_pawn_move(state)
        if (
            last_move is None
            or last_move.player == pawn.color
            or last_move.to_row != row
            or last_move.to_col != target_col
        ):
            return None
        victim = state.board.grid[row][target_col]
        if victim is None or victim.type != "pawn" or victim.color == pawn.color:
            return None
        return row, target_col, victim

    def generate_moves(
        self,
        state: GameState,
        row: int,
        col: int,
        helper,
        params: dict,
    ) -> list[MoveOption]:
        pawn = state.board.grid[row][col]
        if pawn is None or pawn.type != "pawn" or pawn.color == "neutral":
            return []
        direction = -1 if pawn.color == "white" else 1
        options: list[MoveOption] = []
        for target_col in (col - 1, col + 1):
            target_row = row + direction
            if not (0 <= target_row < state.board.rows and 0 <= target_col < state.board.cols):
                continue
            capture = self._capture(
                state,
                row,
                col,
                target_row,
                target_col,
                pawn,
            )
            if capture is None:
                continue
            capture_row, capture_col, victim = capture
            options.append(
                MoveOption(
                    from_row=row,
                    from_col=col,
                    to_row=target_row,
                    to_col=target_col,
                    captures=[
                        CaptureEvent(
                            row=capture_row,
                            col=capture_col,
                            piece=victim,
                            reason="En passant",
                        )
                    ],
                    explanation="En passant capture",
                )
            )
        return options

    def apply(
        self,
        state: GameState,
        move: Move,
        context: RuleContext,
        helper,
        params: dict,
    ) -> None:
        pawn = context.moved_piece
        if (
            pawn is None
            or context.metadata.get("original_piece_type") != "pawn"
            or context.target_piece is not None
        ):
            return
        pre_move = state.clone()
        pre_move.board.grid[move.to_row][move.to_col] = None
        pawn_before = pawn.model_copy(deep=True)
        pawn_before.has_moved = not context.metadata.get("moved_piece_was_unmoved")
        pre_move.board.grid[move.from_row][move.from_col] = pawn_before
        capture = self._capture(
            pre_move,
            move.from_row,
            move.from_col,
            move.to_row,
            move.to_col,
            pawn,
        )
        if capture is None:
            return
        capture_row, capture_col, _ = capture
        victim = state.board.grid[capture_row][capture_col]
        if victim is None:
            return
        state.board.grid[capture_row][capture_col] = None
        context.add_capture(
            row=capture_row,
            col=capture_col,
            piece=victim,
            reason="En passant",
        )
        if not context.simulated:
            context.messages.append("Pawn captured en passant.")


class ClassicDrawRule(Rule):
    id = "classic_draws"
    name = "Classic Draw Rules"
    description = (
        "Classic games draw after threefold repetition, fifty moves by each side without "
        "a Pawn move or capture, or when checkmate is impossible with the remaining material."
    )
    tier = "basic"
    can_disable = False
    apply_in_simulation = False

    @staticmethod
    def _insufficient_material(state: GameState) -> bool:
        non_kings = [
            (row, col, piece)
            for row, board_row in enumerate(state.board.grid)
            for col, piece in enumerate(board_row)
            if piece is not None and piece.type != "king"
        ]
        if not non_kings:
            return True
        if len(non_kings) == 1:
            return non_kings[0][2].type in {"bishop", "knight"}
        if len(non_kings) == 2 and all(piece.type == "bishop" for _, _, piece in non_kings):
            colors = {(row + col) % 2 for row, col, _ in non_kings}
            return len(colors) == 1
        return False

    def apply(
        self,
        state: GameState,
        move: Move,
        context: RuleContext,
        helper,
        params: dict,
    ) -> None:
        if not _uses_classic_draw_rules(state):
            return
        original_type = str(context.metadata.get("original_piece_type", ""))
        state.classic.last_move_irreversible = bool(
            original_type == "pawn"
            or context.captures
            or (
                original_type in IRREVERSIBLE_RIGHTS_TYPES
                and context.metadata.get("moved_piece_was_unmoved")
            )
        )

    def complete_turn(
        self,
        state: GameState,
        acting_color: str,
        helper,
        params: dict,
    ) -> None:
        if not _uses_classic_draw_rules(state) or not state.history:
            state.classic.last_move_irreversible = False
            return
        last_move = state.history[-1]
        irreversible = state.classic.last_move_irreversible or last_move.action_type != "move"
        if last_move.piece == "pawn" or last_move.captures:
            state.classic.halfmove_clock = 0
        else:
            state.classic.halfmove_clock += 1

        side_to_move = _opposing_color(acting_color)
        key = _position_key(state, side_to_move)
        if irreversible:
            state.classic.position_counts = {}
        state.classic.position_counts[key] = state.classic.position_counts.get(key, 0) + 1
        state.classic.last_move_irreversible = False

    def evaluate_state(self, state: GameState, helper, params: dict) -> None:
        if not _uses_classic_draw_rules(state) or state.game_status in FINISHED_STATUSES:
            return
        key = _position_key(state, state.current_player)
        if not state.classic.position_counts:
            state.classic.position_counts[key] = 1

        if self._insufficient_material(state):
            finish_game(
                state,
                status="draw",
                reason_code="insufficient_material",
                trigger="material",
                winner=None,
                description="Draw! Neither side has enough material to deliver checkmate.",
            )
            return
        if state.classic.halfmove_clock >= 100:
            finish_game(
                state,
                status="draw",
                reason_code="fifty_move_rule",
                trigger="move_count",
                winner=None,
                description="Draw! Fifty moves passed for each side without a Pawn move or capture.",
            )
            return
        if state.classic.position_counts.get(key, 0) >= 3:
            finish_game(
                state,
                status="draw",
                reason_code="threefold_repetition",
                trigger="position_repetition",
                winner=None,
                description="Draw! The same position occurred three times.",
            )
