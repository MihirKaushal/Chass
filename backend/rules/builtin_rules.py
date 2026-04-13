from __future__ import annotations

from backend.models import GameState, Move
from backend.rules.base import Rule, RuleContext, ValidationResult


def opposing_color(color: str) -> str:
    return "black" if color == "white" else "white"


class BoundsRule(Rule):
    id = "bounds"
    name = "Board Bounds"
    description = "Moves must stay inside the current board dimensions."
    tier = "basic"
    can_disable = False

    def validate(self, state: GameState, move: Move, helper, params: dict) -> ValidationResult:
        size = state.board.size
        coords = [move.from_row, move.from_col, move.to_row, move.to_col]
        if any(coord < 0 or coord >= size for coord in coords):
            return ValidationResult(is_valid=False, reason="Move is outside board bounds")
        return ValidationResult(is_valid=True)


class PiecePresenceRule(Rule):
    id = "piece_presence"
    name = "Piece Presence"
    description = "A move must start on a square containing a piece."
    tier = "basic"
    can_disable = False

    def validate(self, state: GameState, move: Move, helper, params: dict) -> ValidationResult:
        if state.board.grid[move.from_row][move.from_col] is None:
            return ValidationResult(is_valid=False, reason="No piece found at source square")
        return ValidationResult(is_valid=True)


class TurnRule(Rule):
    id = "turn_order"
    name = "Turn Order"
    description = "Only the active player can move their own pieces."
    tier = "basic"
    can_disable = False

    def validate(self, state: GameState, move: Move, helper, params: dict) -> ValidationResult:
        if state.game_status in {"checkmate", "stalemate"}:
            return ValidationResult(is_valid=False, reason="Game is already finished")

        piece = state.board.grid[move.from_row][move.from_col]
        if piece is None:
            return ValidationResult(is_valid=False, reason="No piece found at source square")
        if piece.color != state.current_player:
            return ValidationResult(
                is_valid=False,
                reason=f"It is {state.current_player}'s turn",
            )
        return ValidationResult(is_valid=True)


class MovementPatternRule(Rule):
    id = "movement_patterns"
    name = "Piece Movement Patterns"
    description = (
        "Piece behavior is validated against its configured movement patterns, "
        "enabling custom piece definitions and board variants."
    )
    tier = "basic"
    can_disable = False

    def validate(self, state: GameState, move: Move, helper, params: dict) -> ValidationResult:
        options = helper.generate_piece_moves(state, move.from_row, move.from_col)
        is_match = any(
            option.to_row == move.to_row and option.to_col == move.to_col for option in options
        )
        if not is_match:
            return ValidationResult(is_valid=False, reason="Move does not match piece behavior")
        return ValidationResult(is_valid=True)


class CaptureRule(Rule):
    id = "capture"
    name = "Capture Rule"
    description = "Captures enemy piece when landing on an occupied enemy square."
    tier = "basic"
    can_disable = False

    def apply(
        self,
        state: GameState,
        move: Move,
        context: RuleContext,
        helper,
        params: dict,
    ) -> None:
        if context.target_piece is None or context.moved_piece is None:
            return
        if context.target_piece.color == context.moved_piece.color:
            return

        context.add_capture(
            row=move.to_row,
            col=move.to_col,
            piece=context.target_piece,
            reason="Standard capture",
        )


class CheckRule(Rule):
    id = "check"
    name = "Check Rule"
    description = "Moves are illegal if they leave your king in check; game state marks check."
    tier = "basic"
    can_disable = False

    def validate(
        self,
        state: GameState,
        move: Move,
        helper,
        params: dict,
    ) -> ValidationResult:
        source_piece = state.board.grid[move.from_row][move.from_col]
        if source_piece is None:
            return ValidationResult(is_valid=False, reason="No piece found at source square")

        target_piece = state.board.grid[move.to_row][move.to_col]
        if target_piece is not None and target_piece.type == "king":
            return ValidationResult(
                is_valid=False,
                reason="Illegal move: kings cannot be captured directly",
            )

        simulated_state = helper.simulate_move_for_validation(state, move)
        if helper.is_king_in_check(simulated_state, source_piece.color):
            return ValidationResult(
                is_valid=False,
                reason="Illegal move: your king would remain in check",
            )

        return ValidationResult(is_valid=True)

    def evaluate_state(self, state: GameState, helper, params: dict) -> None:
        state.winner = None

        king_position = helper.find_king(state, state.current_player)
        if king_position is None:
            state.game_status = "checkmate"
            state.winner = opposing_color(state.current_player)
            return

        in_check = helper.is_king_in_check(state, state.current_player)
        state.game_status = "check" if in_check else "active"


class CheckmateRule(Rule):
    id = "checkmate"
    name = "Checkmate Rule"
    description = "Checkmate occurs when checked side has no legal move to escape."
    tier = "basic"
    can_disable = False
    apply_in_simulation = False

    def evaluate_state(self, state: GameState, helper, params: dict) -> None:
        if state.game_status != "check":
            return

        legal_moves = helper.get_valid_moves_for_color(state, state.current_player)
        if legal_moves:
            return

        state.game_status = "checkmate"
        state.winner = opposing_color(state.current_player)


class StalemateRule(Rule):
    id = "stalemate"
    name = "Stalemate Rule"
    description = "Stalemate occurs when side to move has no legal moves but is not in check."
    tier = "basic"
    can_disable = False
    apply_in_simulation = False

    def evaluate_state(self, state: GameState, helper, params: dict) -> None:
        if state.game_status != "active":
            return

        legal_moves = helper.get_valid_moves_for_color(state, state.current_player)
        if legal_moves:
            return

        state.game_status = "stalemate"
        state.winner = None


class ScoreRule(Rule):
    id = "score"
    name = "Score Rule"
    description = "Computes material score from piece metadata values."
    tier = "basic"
    can_disable = False
    apply_in_simulation = False

    def evaluate_state(self, state: GameState, helper, params: dict) -> None:
        white_score = 0
        black_score = 0

        for row in state.board.grid:
            for piece in row:
                if piece is None or piece.points is None:
                    continue
                if piece.color == "white":
                    white_score += piece.points
                else:
                    black_score += piece.points

        state.score = {"white": white_score, "black": black_score}


class DoubleCaptureRookRule(Rule):
    id = "double_capture_rook"
    name = "Double Capture Rule"
    description = (
        "If a rook moves and two enemy pieces are directly aligned in the move "
        "direction, both are captured."
    )
    tier = "advanced"
    can_disable = True

    def apply(
        self,
        state: GameState,
        move: Move,
        context: RuleContext,
        helper,
        params: dict,
    ) -> None:
        def _safe_int(value: object, default: int) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        moved_piece = state.board.grid[move.to_row][move.to_col]
        if moved_piece is None or moved_piece.type != "rook":
            return

        delta_row = move.to_row - move.from_row
        delta_col = move.to_col - move.from_col
        step_row = 0 if delta_row == 0 else (1 if delta_row > 0 else -1)
        step_col = 0 if delta_col == 0 else (1 if delta_col > 0 else -1)

        if step_row != 0 and step_col != 0:
            return
        if step_row == 0 and step_col == 0:
            return

        aligned_enemies = max(2, _safe_int(params.get("alignedEnemies", 2), 2))
        capture_count = max(1, _safe_int(params.get("captureCount", 2), 2))
        size = state.board.size

        enemy_chain: list[tuple[int, int, object]] = []
        for step in range(1, aligned_enemies + 1):
            check_row = move.to_row + (step * step_row)
            check_col = move.to_col + (step * step_col)

            if not (0 <= check_row < size and 0 <= check_col < size):
                return

            target_piece = state.board.grid[check_row][check_col]
            if target_piece is None or target_piece.color == moved_piece.color:
                return

            enemy_chain.append((check_row, check_col, target_piece))

        captures_to_apply = enemy_chain[: min(capture_count, len(enemy_chain))]

        for row, col, target_piece in captures_to_apply:
            state.board.grid[row][col] = None
            context.add_capture(
                row=row,
                col=col,
                piece=target_piece,
                reason=self.name,
            )

        if not context.simulated:
            context.messages.append(
                "Rook captured "
                f"{min(capture_count, len(enemy_chain))} pieces due to Double Capture Rule"
            )


classic_chess_rules: list[Rule] = [
    BoundsRule(),
    PiecePresenceRule(),
    TurnRule(),
    MovementPatternRule(),
    CheckRule(),
    CaptureRule(),
    CheckmateRule(),
    StalemateRule(),
    ScoreRule(),
]

variant_rules: list[Rule] = [
    DoubleCaptureRookRule(),
]
