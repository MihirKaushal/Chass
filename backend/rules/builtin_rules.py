from __future__ import annotations

from backend.models import GameState, Move
from backend.rules.base import Rule, RuleContext, ValidationResult
from backend.rules.variant_system import (
    FINISHED_STATUSES,
    affinity_start_squares,
    direct_king_capture_allowed,
    finish_game,
    has_ability,
    objective_center_squares,
    piece_runtime_active,
    uses_royal_safety,
)


def opposing_color(color: str) -> str:
    return "black" if color == "white" else "white"


class BoundsRule(Rule):
    id = "bounds"
    name = "Board Bounds"
    description = "Moves must stay inside the current board dimensions."
    tier = "basic"
    can_disable = False

    def validate(self, state: GameState, move: Move, helper, params: dict) -> ValidationResult:
        if any(
            [
                move.from_row < 0,
                move.from_row >= state.board.rows,
                move.to_row < 0,
                move.to_row >= state.board.rows,
                move.from_col < 0,
                move.from_col >= state.board.cols,
                move.to_col < 0,
                move.to_col >= state.board.cols,
            ]
        ):
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
        if state.game_status in FINISHED_STATUSES:
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
        if context.moved_piece.type == "cannibal":
            return
        if context.target_piece.color == context.moved_piece.color:
            return

        context.add_capture(
            row=move.to_row,
            col=move.to_col,
            piece=context.target_piece,
            reason="Standard capture",
        )


class CannibalRule(Rule):
    id = "cannibal_consumption"
    name = "Cannibal Consumption"
    description = (
        "Cannibals consume pieces behind them and borrow the victim's movement for five moves."
    )
    tier = "basic"
    can_disable = False

    @staticmethod
    def _clear_form(piece) -> None:
        for key in (
            "cannibal_form",
            "cannibal_form_name",
            "cannibal_moves_remaining",
            "cannibal_super_state",
        ):
            piece.runtime.pop(key, None)

    def validate(
        self,
        state: GameState,
        move: Move,
        helper,
        params: dict,
    ) -> ValidationResult:
        piece = state.board.grid[move.from_row][move.from_col]
        if piece is None or piece.type != "cannibal":
            return ValidationResult(is_valid=True)
        target = state.board.grid[move.to_row][move.to_col]
        if int(piece.runtime.get("cannibal_moves_remaining", 0)) > 0:
            if target is not None:
                return ValidationResult(
                    is_valid=False,
                    reason="A powered Cannibal cannot consume another piece.",
                )
            return ValidationResult(is_valid=True)
        if target is None:
            return ValidationResult(is_valid=True)

        backward = 1 if piece.color == "white" else -1
        if move.to_row - move.from_row != backward or abs(move.to_col - move.from_col) > 1:
            return ValidationResult(
                is_valid=False,
                reason="A Cannibal can consume only directly or diagonally behind itself.",
            )
        if target.type in {"barricade", "diplomat"} or piece_runtime_active(
            state,
            target,
            "capture_immune_until_turn",
        ):
            return ValidationResult(is_valid=False, reason="That piece cannot be consumed.")
        return ValidationResult(is_valid=True)

    def apply(
        self,
        state: GameState,
        move: Move,
        context: RuleContext,
        helper,
        params: dict,
    ) -> None:
        piece = context.moved_piece
        if piece is None or piece.type != "cannibal":
            return

        remaining = int(piece.runtime.get("cannibal_moves_remaining", 0))
        if remaining > 0:
            remaining -= 1
            if remaining:
                piece.runtime["cannibal_moves_remaining"] = remaining
            else:
                previous_form = str(piece.runtime.get("cannibal_form_name", "borrowed"))
                self._clear_form(piece)
                if not context.simulated:
                    context.messages.append(
                        f"Cannibal's {previous_form} mobility expired."
                    )
            return

        target = context.target_piece
        if target is None:
            return
        context.add_capture(
            row=move.to_row,
            col=move.to_col,
            piece=target,
            reason="Cannibal consumption",
        )
        super_state = target.type == "cannibal"
        inherited_type = "queen" if super_state else target.type
        inherited_definition = state.piece_definitions.get(inherited_type)
        inherited_name = (
            inherited_definition.display_name
            if inherited_definition is not None
            else inherited_type.title()
        )
        piece.runtime["cannibal_form"] = inherited_type
        piece.runtime["cannibal_form_name"] = inherited_name
        piece.runtime["cannibal_moves_remaining"] = 5
        piece.runtime["cannibal_super_state"] = super_state
        if not context.simulated:
            if super_state:
                context.messages.append(
                    "Cannibal consumed another Cannibal and entered Super State with "
                    "Queen mobility for 5 moves."
                )
            else:
                allegiance = "allied" if target.color == piece.color else "enemy"
                context.messages.append(
                    f"Cannibal consumed an {allegiance} {target.name} and borrowed "
                    f"{inherited_name} mobility for 5 moves."
                )


class PromotionRule(Rule):
    id = "promotion"
    name = "Pawn Promotion"
    description = (
        "A pawn reaching the final rank promotes to a queen, rook, bishop, or knight."
    )
    tier = "basic"
    can_disable = False

    def validate(
        self,
        state: GameState,
        move: Move,
        helper,
        params: dict,
    ) -> ValidationResult:
        if move.promotion is None:
            return ValidationResult(is_valid=True)
        piece = state.board.grid[move.from_row][move.from_col]
        if piece is None or piece.type != "pawn":
            return ValidationResult(
                is_valid=False,
                reason="Only a Pawn reaching the final rank can promote.",
            )
        promotion_row = 0 if piece.color == "white" else state.board.rows - 1
        if move.to_row != promotion_row:
            return ValidationResult(
                is_valid=False,
                reason="A Pawn can promote only on the final rank.",
            )
        if (
            move.promotion == "kamikaze"
            and not has_ability(state, piece.color, "kamikaze")
        ):
            return ValidationResult(
                is_valid=False,
                reason="Kamikaze is not this player's selected ability.",
            )
        if move.promotion != "kamikaze" and move.promotion not in state.piece_definitions:
            return ValidationResult(
                is_valid=False,
                reason=f"{move.promotion.title()} promotion is unavailable.",
            )
        return ValidationResult(is_valid=True)

    def apply(
        self,
        state: GameState,
        move: Move,
        context: RuleContext,
        helper,
        params: dict,
    ) -> None:
        piece = state.board.grid[move.to_row][move.to_col]
        if piece is None or piece.type != "pawn":
            return
        promotion_row = 0 if piece.color == "white" else state.board.rows - 1
        if move.to_row != promotion_row:
            return

        if (
            move.promotion == "kamikaze"
            and has_ability(state, piece.color, "kamikaze")
        ):
            state.board.grid[move.to_row][move.to_col] = None
            enemy_king_hit = False
            for direction in (-1, 1):
                for distance in (1, 2):
                    target_col = move.to_col + direction * distance
                    if not 0 <= target_col < state.board.cols:
                        break
                    target = state.board.grid[move.to_row][target_col]
                    if target is not None and target.type == "barricade":
                        break
                    if (
                        target is None
                        or target.color == piece.color
                        or target.type == "diplomat"
                        or piece_runtime_active(
                            state,
                            target,
                            "capture_immune_until_turn",
                        )
                    ):
                        continue
                    state.board.grid[move.to_row][target_col] = None
                    context.add_capture(
                        row=move.to_row,
                        col=target_col,
                        piece=target,
                        reason="Kamikaze blast",
                    )
                    enemy_king_hit = enemy_king_hit or target.type == "king"
            if not context.simulated:
                context.messages.append("Pawn detonated with Kamikaze.")
            if enemy_king_hit:
                finish_game(
                    state,
                    status="checkmate",
                    reason_code="kamikaze",
                    trigger="special_ability",
                    winner=piece.color,
                    description=(
                        f"{piece.color.title()} won! A Kamikaze Pawn destroyed "
                        f"{opposing_color(piece.color).title()}'s King."
                    ),
                )
            return

        promoted_type = move.promotion or "queen"
        definition = state.piece_definitions.get(promoted_type)
        if definition is None:
            return

        piece.type = promoted_type
        piece.name = definition.display_name
        piece.points = definition.points
        piece.has_moved = True
        piece.is_custom = definition.is_custom
        piece.custom_attributes = dict(definition.custom_attributes)
        if not context.simulated:
            context.messages.append(
                f"Pawn promoted to {definition.display_name}."
            )


class CheckRule(Rule):
    id = "check"
    name = "Check Rule"
    description = "Moves are illegal if they leave your king in check; game state marks check."
    tier = "basic"
    can_disable = True

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

        if not uses_royal_safety(state):
            return ValidationResult(is_valid=True)

        target_piece = state.board.grid[move.to_row][move.to_col]
        if (
            target_piece is not None
            and target_piece.type == "king"
            and not direct_king_capture_allowed(state)
        ):
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

        if not uses_royal_safety(state):
            state.game_status = "active"
            return

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
    can_disable = True
    apply_in_simulation = False

    def evaluate_state(self, state: GameState, helper, params: dict) -> None:
        if not uses_royal_safety(state):
            return
        if state.game_status != "check":
            return

        if helper.has_any_legal_move(
            state,
            state.current_player,
        ) or helper.has_legal_alternative_action(
            state,
            state.current_player,
        ):
            return

        state.game_status = "checkmate"
        state.winner = opposing_color(state.current_player)
        if state.configuration.victory.mode != "royal_score":
            winner = state.winner
            finish_game(
                state,
                status="checkmate",
                reason_code="checkmate",
                trigger="royal_defeat",
                winner=winner,
                description=(
                    f"{winner.title()} won! {winner.title()} checkmated "
                    f"{state.current_player.title()}'s King."
                ),
            )


class StalemateRule(Rule):
    id = "stalemate"
    name = "Stalemate Rule"
    description = "Stalemate occurs when side to move has no legal moves but is not in check."
    tier = "basic"
    can_disable = True
    apply_in_simulation = False

    def evaluate_state(self, state: GameState, helper, params: dict) -> None:
        if state.game_status != "active":
            return

        if helper.has_any_legal_move(
            state,
            state.current_player,
        ) or helper.has_legal_alternative_action(
            state,
            state.current_player,
        ):
            return

        state.game_status = "stalemate"
        state.winner = None
        state.result = None
        finish_game(
            state,
            status="stalemate",
            reason_code="stalemate",
            trigger="no_legal_actions",
            winner=None,
            description="Stalemate! Neither player won because the active side has no legal action.",
        )


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

        for piece in state.captured_pieces.get("white", []):
            if piece.points is None:
                continue
            white_score += piece.points

        for piece in state.captured_pieces.get("black", []):
            if piece.points is None:
                continue
            black_score += piece.points

        state.score = {
            "white": max(0, white_score - state.spent_score.get("white", 0)),
            "black": max(0, black_score - state.spent_score.get("black", 0)),
        }


class ConfigurableVictoryRule(Rule):
    id = "configured_victory"
    name = "Configured Victory"
    description = "Resolves the selected end-game condition and produces a clear result."
    tier = "basic"
    can_disable = False
    apply_in_simulation = False

    @staticmethod
    def _missing_king(state: GameState, color: str) -> bool:
        return not any(
            piece is not None and piece.type == "king" and piece.color == color
            for row in state.board.grid
            for piece in row
        )

    @staticmethod
    def _army_count(state: GameState, color: str) -> int:
        return sum(
            piece is not None and piece.color == color and piece.type != "diplomat"
            for row in state.board.grid
            for piece in row
        )

    def evaluate_state(self, state: GameState, helper, params: dict) -> None:
        if state.phase not in {"play", "finished"}:
            return
        config = state.configuration.victory
        mode = config.mode

        if mode in {"checkmate", "timed"}:
            return

        white_king_missing = self._missing_king(state, "white")
        black_king_missing = self._missing_king(state, "black")

        if mode == "king_capture":
            if not white_king_missing and not black_king_missing:
                return
            winner = None
            if white_king_missing != black_king_missing:
                winner = "black" if white_king_missing else "white"
            finish_game(
                state,
                status="king_capture" if winner else "draw",
                reason_code="king_capture" if winner else "mutual_king_capture",
                trigger="royal_capture",
                winner=winner,
                description=(
                    f"{winner.title()} won! {winner.title()} captured "
                    f"{opposing_color(winner).title()}'s King."
                    if winner
                    else "Draw! Both Kings were removed."
                ),
            )
            return

        if mode == "point_race":
            winners = [
                color
                for color in ("white", "black")
                if state.score[color] >= config.target_points
            ]
            if not winners:
                return
            winner = winners[0] if len(winners) == 1 else None
            finish_game(
                state,
                status="points" if winner else "draw",
                reason_code="point_target" if winner else "simultaneous_point_target",
                trigger="score",
                winner=winner,
                description=(
                    f"{winner.title()} won! {winner.title()} got to "
                    f"{config.target_points} points."
                    if winner
                    else f"Draw! Both players got to {config.target_points} points."
                ),
            )
            return

        if mode == "elimination":
            white_count = self._army_count(state, "white")
            black_count = self._army_count(state, "black")
            if white_count and black_count:
                return
            winner = None
            if bool(white_count) != bool(black_count):
                winner = "white" if white_count else "black"
            finish_game(
                state,
                status="elimination" if winner else "draw",
                reason_code="total_elimination" if winner else "mutual_elimination",
                trigger="army_eliminated",
                winner=winner,
                description=(
                    f"{winner.title()} won by eliminating every opposing combat piece."
                    if winner
                    else "Draw! Both armies were eliminated."
                ),
            )


            return

        if mode == "royal_score" and (
            state.game_status == "checkmate" or white_king_missing or black_king_missing
        ):
            white_score = state.score["white"]
            black_score = state.score["black"]
            winner = None
            if white_score != black_score:
                winner = "white" if white_score > black_score else "black"
            finish_game(
                state,
                status="royal_score" if winner else "draw",
                reason_code="royal_score" if winner else "royal_score_tie",
                trigger="royal_defeat",
                winner=winner,
                description=(
                    f"{winner.title()} won the Royal Score match with "
                    f"{state.score[winner]} points."
                    if winner
                    else f"Draw! Royal defeat ended the match at {white_score} points each."
                ),
            )


class CenterDominionRule(Rule):
    id = "center_dominion"
    name = "Center Dominion"
    description = (
        "Hold both marked center squares through the opponent's turn for the configured "
        "number of consecutive rounds."
    )
    tier = "basic"
    can_disable = False
    apply_in_simulation = False

    @staticmethod
    def squares(state: GameState) -> dict[str, list[tuple[int, int]]]:
        return affinity_start_squares(state.board.rows, state.board.cols)

    def controls(self, state: GameState, color: str) -> bool:
        return all(
            (piece := state.board.grid[row][col]) is not None and piece.color == color
            for row, col in self.squares(state)[color]
        )

    def complete_turn(self, state: GameState, acting_color: str, helper, params: dict) -> None:
        if state.configuration.victory.mode != "center_dominion":
            return

        opponent = opposing_color(acting_color)
        opponent_controls = self.controls(state, opponent)
        if state.center_dominion.primed[opponent] and opponent_controls:
            state.center_dominion.progress[opponent] += 1
        elif not opponent_controls:
            state.center_dominion.progress[opponent] = 0
        state.center_dominion.primed[opponent] = False

        acting_controls = self.controls(state, acting_color)
        if not acting_controls:
            state.center_dominion.progress[acting_color] = 0
        state.center_dominion.primed[acting_color] = acting_controls

    def evaluate_state(self, state: GameState, helper, params: dict) -> None:
        if state.configuration.victory.mode != "center_dominion":
            return
        if state.game_status in FINISHED_STATUSES:
            return
        target = state.configuration.victory.dominion_rounds
        winner = next(
            (
                color
                for color in ("white", "black")
                if state.center_dominion.progress[color] >= target
            ),
            None,
        )
        if winner is None:
            return
        finish_game(
            state,
            status="center_dominion",
            reason_code="center_dominion",
            trigger="center_control",
            winner=winner,
            description=(
                f"{winner.title()} won! {winner.title()} held both center squares for "
                f"{target} consecutive rounds."
            ),
        )


class RoyalCenterRule(Rule):
    id = "royal_center"
    name = "Royal Center"
    description = "Win when your King legally reaches one of the four marked center squares."
    tier = "basic"
    can_disable = False
    apply_in_simulation = False

    @staticmethod
    def squares(state: GameState) -> list[tuple[int, int]]:
        return objective_center_squares(state.board.rows, state.board.cols)

    def evaluate_state(self, state: GameState, helper, params: dict) -> None:
        if state.configuration.victory.mode != "royal_center":
            return
        if state.game_status in FINISHED_STATUSES:
            return

        targets = set(self.squares(state))
        winners = [
            color
            for color in ("white", "black")
            if (king := helper.find_king(state, color)) is not None and king in targets
        ]
        if not winners:
            return
        last_player = state.history[-1].player if state.history else None
        winner = last_player if last_player in winners else winners[0]
        finish_game(
            state,
            status="royal_center",
            reason_code="royal_center",
            trigger="king_reached_center",
            winner=winner,
            description=(
                f"{winner.title()} won! {winner.title()}'s King reached the center."
            ),
        )


class CheckRaceRule(Rule):
    id = "check_race"
    name = "Check Race"
    description = "Win by checking the opposing King the configured number of times."
    tier = "basic"
    can_disable = False
    apply_in_simulation = False

    def complete_turn(self, state: GameState, acting_color: str, helper, params: dict) -> None:
        if state.configuration.victory.mode != "check_race":
            return
        if helper.is_king_in_check(state, opposing_color(acting_color)):
            state.check_race.checks[acting_color] += 1

    def evaluate_state(self, state: GameState, helper, params: dict) -> None:
        if state.configuration.victory.mode != "check_race":
            return
        if state.game_status in FINISHED_STATUSES:
            return
        target = state.configuration.victory.check_target
        winner = next(
            (
                color
                for color in ("white", "black")
                if state.check_race.checks[color] >= target
            ),
            None,
        )
        if winner is None:
            return
        finish_game(
            state,
            status="check_race",
            reason_code="check_race",
            trigger="check_count",
            winner=winner,
            description=(
                f"{winner.title()} won! {winner.title()} checked the opposing King "
                f"{target} time{'s' if target != 1 else ''}."
            ),
        )


class ScoreTargetWinRule(Rule):
    id = "score_target_win"
    name = "Score Target Win Rule"
    description = (
        "A player wins when their captured score reaches a configured target "
        "(for example, first to 21 points)."
    )
    tier = "advanced"
    can_disable = True
    apply_in_simulation = False

    def evaluate_state(self, state: GameState, helper, params: dict) -> None:
        if state.game_status in FINISHED_STATUSES:
            return

        try:
            target_score = int(params.get("targetScore", 21))
        except (TypeError, ValueError):
            target_score = 21

        target_score = max(1, target_score)

        winners = [
            color
            for color in ("white", "black")
            if state.score.get(color, 0) >= target_score
        ]
        if not winners:
            return

        winner = winners[0] if len(winners) == 1 else None
        finish_game(
            state,
            status="score_target" if winner else "draw",
            reason_code="score_target" if winner else "simultaneous_score_target",
            trigger="score",
            winner=winner,
            description=(
                f"{winner.title()} won! {winner.title()} got to {target_score} points."
                if winner
                else f"Draw! Both players got to {target_score} points."
            ),
        )


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

        enemy_chain: list[tuple[int, int, object]] = []
        for step in range(1, aligned_enemies + 1):
            check_row = move.to_row + (step * step_row)
            check_col = move.to_col + (step * step_col)

            if not (
                0 <= check_row < state.board.rows and 0 <= check_col < state.board.cols
            ):
                return

            target_piece = state.board.grid[check_row][check_col]
            if (
                target_piece is None
                or target_piece.color == moved_piece.color
                or target_piece.type in {"barricade", "diplomat"}
                or piece_runtime_active(
                    state,
                    target_piece,
                    "capture_immune_until_turn",
                )
            ):
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
    CannibalRule(),
    PromotionRule(),
    ScoreRule(),
    CenterDominionRule(),
    RoyalCenterRule(),
    CheckRaceRule(),
    CheckmateRule(),
    ConfigurableVictoryRule(),
    StalemateRule(),
]

variant_rules: list[Rule] = [
    DoubleCaptureRookRule(),
    ScoreTargetWinRule(),
]
