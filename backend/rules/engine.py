from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from backend.models import GameState, Move, MoveOption, MoveRecord, Piece, RuleSetting
from backend.rules.base import Rule, RuleContext, ValidationResult
from backend.rules.builtin_rules import classic_chess_rules, opposing_color, variant_rules
from backend.rules.configuration import ConfigurationRuleEngine
from backend.rules.gambit_rules import GambitRuleSet
from backend.rules.movement import generate_piece_attacks, generate_piece_moves
from backend.rules.variant_system import (
    FINISHED_STATUSES,
    VariantActionRules,
    finish_game,
    has_ability,
    process_end_of_turn_effects,
    trigger_power_of_love,
)


class RuleEngine:
    def __init__(self) -> None:
        # Optional victory modifiers must resolve before the final no-action
        # fallback, otherwise a scoring move could be reported as stalemate.
        stalemate_rules = [rule for rule in classic_chess_rules if rule.id == "stalemate"]
        ordered_rules: list[Rule] = [
            *(rule for rule in classic_chess_rules if rule.id != "stalemate"),
            *variant_rules,
            *stalemate_rules,
        ]
        self._rule_order = [rule.id for rule in ordered_rules]
        self._rules: dict[str, Rule] = {rule.id: rule for rule in ordered_rules}
        self._default_enabled: dict[str, bool] = {
            rule.id: True for rule in ordered_rules
        }
        self._default_enabled["double_capture_rook"] = False
        self._default_enabled["score_target_win"] = False
        self.gambit = GambitRuleSet()
        self.actions = VariantActionRules()
        self.configuration = ConfigurationRuleEngine()
        self.center_dominion = next(
            rule for rule in ordered_rules if rule.id == "center_dominion"
        )
        self.royal_center = next(
            rule for rule in ordered_rules if rule.id == "royal_center"
        )

    def generate_piece_moves(self, state: GameState, row: int, col: int) -> list[MoveOption]:
        options = generate_piece_moves(state, row, col)
        for rule, setting in self._iter_enabled_rules(state):
            options.extend(
                rule.generate_moves(state, row, col, self, setting.params)
            )
        return list({(option.to_row, option.to_col): option for option in options}.values())

    def generate_piece_attacks(
        self,
        state: GameState,
        row: int,
        col: int,
    ) -> set[tuple[int, int]]:
        attacks = generate_piece_attacks(state, row, col)
        for rule, setting in self._iter_enabled_rules(state):
            attacks.update(
                rule.generate_attacks(state, row, col, self, setting.params)
            )
        return attacks

    def available_rules(self) -> list[Rule]:
        return [self._rules[rule_id] for rule_id in self._rule_order]

    def rule_exists(self, rule_id: str) -> bool:
        return rule_id in self._rules

    def default_rule_settings(self) -> list[RuleSetting]:
        return [
            RuleSetting(
                id=rule.id,
                enabled=self._default_enabled.get(rule.id, True),
                params={},
            )
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
            if not rule.can_disable or setting.enabled:
                yield rule, setting

    def _apply_base_move(self, state: GameState, move: Move) -> tuple[RuleContext, Piece]:
        moving_piece = state.board.grid[move.from_row][move.from_col]
        target_piece = state.board.grid[move.to_row][move.to_col]
        if moving_piece is None:
            raise ValueError("No piece found at source square")

        moved_piece_was_unmoved = not moving_piece.has_moved
        original_piece_type = moving_piece.type
        state.board.grid[move.from_row][move.from_col] = None
        moving_piece.has_moved = True
        state.board.grid[move.to_row][move.to_col] = moving_piece
        return (
            RuleContext(
                moved_piece=moving_piece,
                target_piece=target_piece,
                simulated=False,
                metadata={
                    "moved_piece_was_unmoved": moved_piece_was_unmoved,
                    "original_piece_type": original_piece_type,
                },
            ),
            moving_piece,
        )

    def simulate_move_for_validation(self, state: GameState, move: Move) -> GameState:
        simulated = state.clone()
        context, moving_piece = self._apply_base_move(simulated, move)
        context.simulated = True
        for rule, setting in self._iter_enabled_rules(simulated):
            if rule.apply_in_simulation:
                rule.apply(simulated, move, context, self, setting.params)
        if context.captures:
            trigger_power_of_love(simulated, context.captures)
        process_end_of_turn_effects(simulated, moving_piece.color)
        return simulated

    def validate_move(self, state: GameState, move: Move) -> ValidationResult:
        if state.phase != "play":
            return ValidationResult(
                is_valid=False,
                reason="Pieces can move only after setup is complete.",
            )
        for rule, setting in self._iter_enabled_rules(state):
            validation = rule.validate(state, move, self, setting.params)
            if not validation.is_valid:
                return validation
        return ValidationResult(is_valid=True)

    def find_king(self, state: GameState, color: str) -> tuple[int, int] | None:
        for row_idx, row in enumerate(state.board.grid):
            for col_idx, piece in enumerate(row):
                if piece is not None and piece.type == "king" and piece.color == color:
                    return row_idx, col_idx
        return None

    def is_square_attacked_by_color(
        self,
        state: GameState,
        row: int,
        col: int,
        attacker_color: str,
    ) -> bool:
        return any(
            (row, col) in self.generate_piece_attacks(state, source_row, source_col)
            for source_row, board_row in enumerate(state.board.grid)
            for source_col, piece in enumerate(board_row)
            if piece is not None and piece.color == attacker_color
        )

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
        if state.phase not in {"play", "finished"}:
            return []
        if state.game_status in FINISHED_STATUSES:
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
                    moves = [
                        Move(
                            fromRow=row,
                            fromCol=col,
                            toRow=candidate.to_row,
                            toCol=candidate.to_col,
                        )
                    ]
                    if (
                        piece.type == "pawn"
                        and has_ability(work_state, color, "kamikaze")
                        and candidate.to_row
                        == (0 if color == "white" else work_state.board.rows - 1)
                    ):
                        moves.append(
                            Move(
                                fromRow=row,
                                fromCol=col,
                                toRow=candidate.to_row,
                                toCol=candidate.to_col,
                                promotion="kamikaze",
                            )
                        )
                    if any(self.validate_move(work_state, move).is_valid for move in moves):
                        valid_moves.append(candidate)
        return valid_moves

    def get_valid_moves_for_current_player(self, state: GameState) -> list[MoveOption]:
        return self.get_valid_moves_for_color(state, state.current_player)

    def has_any_legal_move(self, state: GameState, color: str) -> bool:
        if state.phase not in {"play", "finished"} or state.game_status in FINISHED_STATUSES:
            return False
        work_state = state.clone()
        work_state.current_player = color
        for row in range(work_state.board.rows):
            for col in range(work_state.board.cols):
                piece = work_state.board.grid[row][col]
                if piece is None or piece.color != color:
                    continue
                for candidate in self.generate_piece_moves(work_state, row, col):
                    moves = [
                        Move(
                            fromRow=row,
                            fromCol=col,
                            toRow=candidate.to_row,
                            toCol=candidate.to_col,
                        )
                    ]
                    if (
                        piece.type == "pawn"
                        and has_ability(work_state, color, "kamikaze")
                        and candidate.to_row
                        == (0 if color == "white" else work_state.board.rows - 1)
                    ):
                        moves.append(
                            Move(
                                fromRow=row,
                                fromCol=col,
                                toRow=candidate.to_row,
                                toCol=candidate.to_col,
                                promotion="kamikaze",
                            )
                        )
                    if any(self.validate_move(work_state, move).is_valid for move in moves):
                        return True
        return False

    def get_available_actions(self, state: GameState, color: str | None = None) -> list[dict]:
        action_color = color or state.current_player
        return self.actions.available_actions(state, action_color, self)

    def has_legal_alternative_action(self, state: GameState, color: str) -> bool:
        command_power = (
            state.configuration.custom_rules.affinity_enabled
            and state.phase == "play"
            and self.gambit.has_legal_power(state, color, self)
        )
        return command_power or self.actions.has_legal_action(state, color, self)

    def clock_snapshot(self, state: GameState) -> dict | None:
        if state.clock is None:
            return None
        remaining = dict(state.clock.remaining_seconds)
        snapshot_at = state.clock.turn_started_at
        if state.phase == "play" and state.game_status not in FINISHED_STATUSES:
            snapshot_at = datetime.now(timezone.utc)
            elapsed = max(
                0.0,
                (snapshot_at - state.clock.turn_started_at).total_seconds(),
            )
            active = state.clock.active_color
            remaining[active] = max(0.0, remaining[active] - elapsed)
        return {
            "initialSeconds": state.clock.initial_seconds,
            "remainingSeconds": remaining,
            "activeColor": state.clock.active_color,
            "turnStartedAt": snapshot_at,
        }

    def refresh_clock(self, state: GameState) -> None:
        if (
            state.clock is None
            or state.phase != "play"
            or state.game_status in FINISHED_STATUSES
        ):
            return
        now = datetime.now(timezone.utc)
        active = state.clock.active_color
        elapsed = max(0.0, (now - state.clock.turn_started_at).total_seconds())
        state.clock.remaining_seconds[active] = max(
            0.0,
            state.clock.remaining_seconds[active] - elapsed,
        )
        state.clock.turn_started_at = now
        if state.clock.remaining_seconds[active] <= 0:
            winner = opposing_color(active)
            finish_game(
                state,
                status="time",
                reason_code="time_expired",
                trigger="clock",
                winner=winner,
                description=(
                    f"{winner.title()} won! {active.title()} ran out of time."
                ),
            )

    def evaluate_state(self, state: GameState) -> GameState:
        if state.phase == "finished" and state.game_status in FINISHED_STATUSES:
            return state
        if state.phase not in {"play", "finished"}:
            state.game_status = "active"
            state.winner = None
            state.result = None
            return state

        self.refresh_clock(state)
        if state.game_status in FINISHED_STATUSES:
            return state

        state.game_status = "active"
        state.winner = None
        state.result = None
        for rule, setting in self._iter_enabled_rules(state):
            rule.evaluate_state(state, self, setting.params)
        if state.game_status in FINISHED_STATUSES:
            state.phase = "finished"
        return state

    def _complete_turn(self, state: GameState, acting_color: str) -> list[str]:
        messages = process_end_of_turn_effects(state, acting_color)
        state.turn_counts[acting_color] += 1
        for rule, setting in self._iter_enabled_rules(state):
            rule.complete_turn(state, acting_color, self, setting.params)
        self.gambit.complete_turn(state, acting_color)
        if state.clock is not None:
            state.clock.active_color = state.current_player
            state.clock.turn_started_at = datetime.now(timezone.utc)
        return messages

    @staticmethod
    def _append_status(explanation: str, state: GameState) -> str:
        if state.result is not None:
            return f"{explanation} {state.result.description}"
        if state.game_status == "check":
            return f"{explanation} {state.current_player.title()} King is in check."
        return explanation

    def apply_move(self, state: GameState, move: Move) -> tuple[GameState, str]:
        working = state.clone()
        self.refresh_clock(working)
        if working.game_status in FINISHED_STATUSES:
            raise ValueError(working.result.description if working.result else "Game is finished.")

        validation = self.validate_move(working, move)
        if not validation.is_valid:
            raise ValueError(validation.reason or "Move rejected by rules")

        next_state = working.clone()
        context, moving_piece = self._apply_base_move(next_state, move)
        for rule, setting in self._iter_enabled_rules(next_state):
            rule.apply(next_state, move, context, self, setting.params)

        if context.captures:
            scored_captures = [
                capture
                for capture in context.captures
                if capture.piece.color != moving_piece.color
            ]
            next_state.captured_pieces[moving_piece.color].extend(
                capture.piece for capture in scored_captures
            )
            trigger_power_of_love(next_state, context.captures)

        if context.messages:
            explanation = " ".join(context.messages)
        elif context.captures:
            explanation = f"{moving_piece.name} captured {len(context.captures)} piece(s)."
        else:
            explanation = f"{moving_piece.name} moved."

        next_state.history.append(
            MoveRecord(
                move_number=next_state.next_move_number(),
                player=moving_piece.color,
                piece=moving_piece.type,
                from_row=move.from_row,
                from_col=move.from_col,
                to_row=move.to_row,
                to_col=move.to_col,
                captures=context.captures,
                explanation=explanation,
            )
        )

        if next_state.phase != "finished":
            effect_messages = self._complete_turn(next_state, moving_piece.color)
            if effect_messages:
                explanation = f"{explanation} {' '.join(effect_messages)}"
            self.evaluate_state(next_state)

        explanation = self._append_status(explanation, next_state)
        next_state.history[-1].explanation = explanation
        return next_state, explanation

    def apply_custom_action(
        self,
        state: GameState,
        color: str,
        payload: dict,
    ) -> tuple[GameState, str]:
        working = state.clone()
        self.refresh_clock(working)
        if working.game_status in FINISHED_STATUSES:
            raise ValueError(working.result.description if working.result else "Game is finished.")
        result = self.actions.apply_action(working, color, payload, self)
        next_state = result.state
        explanation = result.explanation
        effect_messages = self._complete_turn(next_state, color)
        if effect_messages:
            explanation = f"{explanation} {' '.join(effect_messages)}"
        self.evaluate_state(next_state)
        explanation = self._append_status(explanation, next_state)
        next_state.history[-1].explanation = explanation
        return next_state, explanation

    def apply_command_power(
        self,
        state: GameState,
        color: str,
        *,
        power: str,
        row: int,
        col: int,
        evolve_to: str | None,
    ) -> tuple[GameState, str]:
        working = state.clone()
        self.refresh_clock(working)
        next_state, explanation = self.gambit.apply_power(
            working,
            color,
            power=power,
            row=row,
            col=col,
            evolve_to=evolve_to,
            helper=self,
        )
        effect_messages = self._complete_turn(next_state, color)
        if effect_messages:
            explanation = f"{explanation} {' '.join(effect_messages)}"
        self.evaluate_state(next_state)
        explanation = self._append_status(explanation, next_state)
        next_state.history[-1].explanation = explanation
        next_state.affinity.last_power_explanation = explanation
        return next_state, explanation

    def apply_gambit_power(
        self,
        state: GameState,
        color: str,
        *,
        power: str,
        row: int,
        col: int,
        evolve_to: str | None,
    ) -> tuple[GameState, str]:
        """Compatibility alias for clients created before affinity became a custom rule."""
        return self.apply_command_power(
            state,
            color,
            power=power,
            row=row,
            col=col,
            evolve_to=evolve_to,
        )

    @staticmethod
    def _prepare_simulation_state(state: GameState) -> tuple[GameState, dict[str, float] | None]:
        simulated = state.clone()
        remaining = None
        if simulated.clock is not None:
            remaining = dict(simulated.clock.remaining_seconds)
            simulated.clock.turn_started_at = datetime.now(timezone.utc)
        return simulated, remaining

    @staticmethod
    def _restore_simulation_clock(
        state: GameState,
        remaining: dict[str, float] | None,
    ) -> None:
        if state.clock is None or remaining is None:
            return
        state.clock.remaining_seconds = remaining
        state.clock.turn_started_at = datetime.now(timezone.utc)

    def simulate_turn_move(self, state: GameState, move: Move) -> GameState:
        """Apply a complete move without charging wall-clock time to either player."""
        simulated, remaining = self._prepare_simulation_state(state)
        next_state, _ = self.apply_move(simulated, move)
        self._restore_simulation_clock(next_state, remaining)
        return next_state

    def simulate_turn_action(
        self,
        state: GameState,
        color: str,
        payload: dict,
    ) -> GameState:
        """Apply a complete custom action without charging wall-clock time."""
        simulated, remaining = self._prepare_simulation_state(state)
        next_state, _ = self.apply_custom_action(simulated, color, payload)
        self._restore_simulation_clock(next_state, remaining)
        return next_state

    def simulate_command_power(
        self,
        state: GameState,
        color: str,
        *,
        power: str,
        row: int,
        col: int,
        evolve_to: str | None,
    ) -> GameState:
        """Apply a complete command power without charging wall-clock time."""
        simulated, remaining = self._prepare_simulation_state(state)
        next_state, _ = self.apply_command_power(
            simulated,
            color,
            power=power,
            row=row,
            col=col,
            evolve_to=evolve_to,
        )
        self._restore_simulation_clock(next_state, remaining)
        return next_state
