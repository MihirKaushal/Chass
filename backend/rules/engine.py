from __future__ import annotations

from collections.abc import Iterable

from backend.models import GameState, Move, MoveOption, MoveRecord, Piece, RuleSetting
from backend.rules.base import Rule, RuleContext, ValidationResult
from backend.rules.builtin_rules import classic_chess_rules, opposing_color, variant_rules
from backend.rules.movement import generate_piece_moves


class RuleEngine:
    def __init__(self) -> None:
        ordered_rules: list[Rule] = [*classic_chess_rules, *variant_rules]
        self._rule_order = [rule.id for rule in ordered_rules]
        self._rules: dict[str, Rule] = {rule.id: rule for rule in ordered_rules}
        self._default_enabled: dict[str, bool] = {
            rule.id: True for rule in ordered_rules
        }
        self._default_enabled["double_capture_rook"] = False
        self._default_enabled["score_target_win"] = False

    def generate_piece_moves(self, state: GameState, row: int, col: int) -> list[MoveOption]:
        return generate_piece_moves(state, row, col)

    def available_rules(self) -> list[Rule]:
        return [self._rules[rule_id] for rule_id in self._rule_order]

    def rule_exists(self, rule_id: str) -> bool:
        return rule_id in self._rules

    def default_rule_settings(self) -> list[RuleSetting]:
        return [
            RuleSetting(id=rule.id, enabled=self._default_enabled.get(rule.id, True), params={})
            for rule in self.available_rules()
        ]

    def _rule_settings_map(self, state: GameState) -> dict[str, RuleSetting]:
        return {setting.id: setting for setting in state.rules}

    def _iter_enabled_rules(self, state: GameState) -> Iterable[tuple[Rule, RuleSetting]]:
        settings_map = self._rule_settings_map(state)
        for rule in self.available_rules():
            setting = settings_map.get(
                rule.id,
                RuleSetting(
                    id=rule.id,
                    enabled=self._default_enabled.get(rule.id, True),
                    params={},
                ),
            )
            is_enabled = True if not rule.can_disable else setting.enabled
            if is_enabled:
                yield rule, setting

    def _apply_base_move(
        self,
        state: GameState,
        move: Move,
    ) -> tuple[RuleContext, Piece]:
        moving_piece = state.board.grid[move.from_row][move.from_col]
        target_piece = state.board.grid[move.to_row][move.to_col]

        if moving_piece is None:
            raise ValueError("No piece found at source square")

        state.board.grid[move.from_row][move.from_col] = None
        moving_piece.has_moved = True
        state.board.grid[move.to_row][move.to_col] = moving_piece

        context = RuleContext(
            moved_piece=moving_piece,
            target_piece=target_piece,
            simulated=False,
        )

        return context, moving_piece

    def simulate_move_for_validation(self, state: GameState, move: Move) -> GameState:
        simulated = state.clone()
        context, _ = self._apply_base_move(simulated, move)
        context.simulated = True

        for rule, setting in self._iter_enabled_rules(simulated):
            if not rule.apply_in_simulation:
                continue
            rule.apply(simulated, move, context, self, setting.params)

        return simulated

    def validate_move(self, state: GameState, move: Move) -> ValidationResult:
        for rule, setting in self._iter_enabled_rules(state):
            validation = rule.validate(state, move, self, setting.params)
            if not validation.is_valid:
                return validation
        return ValidationResult(is_valid=True)

    def find_king(self, state: GameState, color: str) -> tuple[int, int] | None:
        for row_idx, row in enumerate(state.board.grid):
            for col_idx, piece in enumerate(row):
                if piece is None:
                    continue
                if piece.type == "king" and piece.color == color:
                    return row_idx, col_idx
        return None

    def is_square_attacked_by_color(
        self,
        state: GameState,
        row: int,
        col: int,
        attacker_color: str,
    ) -> bool:
        for r in range(state.board.rows):
            for c in range(state.board.cols):
                piece = state.board.grid[r][c]
                if piece is None or piece.color != attacker_color:
                    continue

                for option in self.generate_piece_moves(state, r, c):
                    if option.to_row == row and option.to_col == col:
                        return True

        return False

    def is_king_in_check(self, state: GameState, color: str) -> bool:
        king_position = self.find_king(state, color)
        if king_position is None:
            return True

        return self.is_square_attacked_by_color(
            state,
            king_position[0],
            king_position[1],
            opposing_color(color),
        )

    def get_valid_moves_for_color(self, state: GameState, color: str) -> list[MoveOption]:
        if state.game_status in {"checkmate", "stalemate"} and color == state.current_player:
            return []

        work_state = state.clone()
        work_state.current_player = color
        valid_moves: list[MoveOption] = []

        for row in range(work_state.board.rows):
            for col in range(work_state.board.cols):
                piece = work_state.board.grid[row][col]
                if piece is None or piece.color != color:
                    continue

                for candidate in self.generate_piece_moves(work_state, row, col):
                    validation = self.validate_move(
                        work_state,
                        Move(
                            fromRow=row,
                            fromCol=col,
                            toRow=candidate.to_row,
                            toCol=candidate.to_col,
                        ),
                    )
                    if validation.is_valid:
                        valid_moves.append(candidate)

        return valid_moves

    def get_valid_moves_for_current_player(self, state: GameState) -> list[MoveOption]:
        return self.get_valid_moves_for_color(state, state.current_player)

    def evaluate_state(self, state: GameState) -> GameState:
        state.game_status = "active"
        state.winner = None
        for rule, setting in self._iter_enabled_rules(state):
            rule.evaluate_state(state, self, setting.params)
        return state

    def apply_move(self, state: GameState, move: Move) -> tuple[GameState, str]:
        validation = self.validate_move(state, move)
        if not validation.is_valid:
            raise ValueError(validation.reason or "Move rejected by rules")

        next_state = state.clone()
        context, moving_piece = self._apply_base_move(next_state, move)

        for rule, setting in self._iter_enabled_rules(next_state):
            rule.apply(next_state, move, context, self, setting.params)

        if context.captures:
            next_state.captured_pieces[moving_piece.color].extend(
                capture.piece for capture in context.captures
            )

        piece_name = moving_piece.name
        capture_count = len(context.captures)

        if context.messages:
            explanation = " ".join(context.messages)
        elif capture_count > 0:
            explanation = f"{piece_name} captured {capture_count} piece(s)."
        else:
            explanation = f"{piece_name} moved."

        move_record = MoveRecord(
            move_number=len(next_state.history) + 1,
            player=moving_piece.color,
            piece=moving_piece.type,
            from_row=move.from_row,
            from_col=move.from_col,
            to_row=move.to_row,
            to_col=move.to_col,
            captures=context.captures,
            explanation=explanation,
        )
        next_state.history.append(move_record)

        next_state.current_player = opposing_color(next_state.current_player)
        self.evaluate_state(next_state)

        if next_state.game_status == "check":
            explanation = f"{explanation} {next_state.current_player.title()} king is in check."
        elif next_state.game_status == "checkmate":
            explanation = (
                f"{explanation} Checkmate. {next_state.winner.title()} wins."
                if next_state.winner
                else f"{explanation} Checkmate."
            )
        elif next_state.game_status == "stalemate":
            explanation = f"{explanation} Stalemate."
        elif next_state.game_status == "score_target":
            explanation = (
                f"{explanation} {next_state.winner.title()} reached the target score."
                if next_state.winner
                else f"{explanation} Score target reached."
            )

        next_state.history[-1].explanation = explanation

        return next_state, explanation
