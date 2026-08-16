from __future__ import annotations

from backend.models import CaptureEvent, GameState, Move, MoveOption, Piece
from backend.rules.base import Rule, RuleContext
from backend.rules.movement import in_bounds
from backend.rules.terrain import is_scorched
from backend.rules.tuning import piece_parameter
from backend.rules.variant_system import (
    direct_king_capture_allowed,
    piece_runtime_active,
)


class ElephantRule(Rule):
    id = "elephant_charge"
    name = "Elephant Charge"
    description = (
        "Elephants move forward or sideways without capturing, or charge through an "
        "exact number of squares and remove pieces in their lane."
    )
    tier = "basic"
    can_disable = False

    @staticmethod
    def _directions(piece: Piece) -> tuple[tuple[int, int], ...]:
        forward = -1 if piece.color == "white" else 1
        return ((forward, 0), (0, -1), (0, 1))

    @staticmethod
    def _lane(
        state: GameState,
        row: int,
        col: int,
        dr: int,
        dc: int,
        distance: int,
    ) -> list[tuple[int, int]] | None:
        lane = [(row + dr * step, col + dc * step) for step in range(1, distance + 1)]
        if not all(
            in_bounds(state.board.rows, state.board.cols, lane_row, lane_col)
            for lane_row, lane_col in lane
        ):
            return None
        return lane

    @staticmethod
    def _uncrossable(state: GameState, piece: Piece) -> bool:
        return piece.type in {"barricade", "diplomat"} or piece_runtime_active(
            state,
            piece,
            "capture_immune_until_turn",
        )

    def _charge_targets(
        self,
        state: GameState,
        piece: Piece,
        lane: list[tuple[int, int]],
        *,
        allow_enemy_king: bool,
    ) -> list[tuple[int, int, Piece]] | None:
        targets: list[tuple[int, int, Piece]] = []
        allied_count = 0
        for target_row, target_col in lane:
            if is_scorched(state, target_row, target_col):
                return None
            target = state.board.grid[target_row][target_col]
            if target is None:
                continue
            if self._uncrossable(state, target):
                return None
            if target.type == "king" and (
                target.color == piece.color or not allow_enemy_king
            ):
                return None
            if target.color == piece.color:
                allied_count += 1
            targets.append((target_row, target_col, target))

        if allied_count > piece_parameter(
            state,
            "elephant",
            "alliedChargeLimit",
        ):
            return None
        return targets

    def generate_moves(
        self,
        state: GameState,
        row: int,
        col: int,
        helper,
        params: dict,
    ) -> list[MoveOption]:
        piece = state.board.grid[row][col]
        if (
            piece is None
            or piece.type != "elephant"
            or piece.color == "neutral"
            or piece_runtime_active(state, piece, "pacified_until_turn")
        ):
            return []

        options: list[MoveOption] = []
        movement_distance = piece_parameter(state, "elephant", "movementDistance")
        charge_distance = piece_parameter(state, "elephant", "chargeDistance")

        for dr, dc in self._directions(piece):
            for distance in range(1, movement_distance + 1):
                target_row = row + dr * distance
                target_col = col + dc * distance
                if not in_bounds(
                    state.board.rows,
                    state.board.cols,
                    target_row,
                    target_col,
                ):
                    break
                if is_scorched(state, target_row, target_col):
                    break
                if state.board.grid[target_row][target_col] is not None:
                    break
                options.append(
                    MoveOption(
                        from_row=row,
                        from_col=col,
                        to_row=target_row,
                        to_col=target_col,
                        explanation="Elephant non-capturing movement",
                    )
                )

            lane = self._lane(state, row, col, dr, dc, charge_distance)
            if lane is None:
                continue
            targets = self._charge_targets(
                state,
                piece,
                lane,
                allow_enemy_king=direct_king_capture_allowed(state),
            )
            if not targets:
                continue
            destination = lane[-1]
            options.append(
                MoveOption(
                    from_row=row,
                    from_col=col,
                    to_row=destination[0],
                    to_col=destination[1],
                    captures=[
                        CaptureEvent(
                            row=target_row,
                            col=target_col,
                            piece=target,
                            reason="Elephant charge",
                        )
                        for target_row, target_col, target in targets
                    ],
                    explanation=(
                        f"Elephant charges through {charge_distance} squares and removes "
                        f"{len(targets)} piece{'s' if len(targets) != 1 else ''}"
                    ),
                )
            )

        return list(
            {
                (option.to_row, option.to_col): option
                for option in options
            }.values()
        )

    def generate_attacks(
        self,
        state: GameState,
        row: int,
        col: int,
        helper,
        params: dict,
    ) -> set[tuple[int, int]]:
        piece = state.board.grid[row][col]
        if (
            piece is None
            or piece.type != "elephant"
            or piece.color == "neutral"
            or piece_runtime_active(state, piece, "pacified_until_turn")
        ):
            return set()

        charge_distance = piece_parameter(state, "elephant", "chargeDistance")
        attacks: set[tuple[int, int]] = set()
        for dr, dc in self._directions(piece):
            lane = self._lane(state, row, col, dr, dc, charge_distance)
            if lane is None:
                continue
            if self._charge_targets(
                state,
                piece,
                lane,
                allow_enemy_king=True,
            ) is not None:
                attacks.update(lane)
        return attacks

    def apply(
        self,
        state: GameState,
        move: Move,
        context: RuleContext,
        helper,
        params: dict,
    ) -> None:
        piece = context.moved_piece
        if piece is None or piece.type != "elephant":
            return

        row_delta = move.to_row - move.from_row
        col_delta = move.to_col - move.from_col
        charge_distance = piece_parameter(state, "elephant", "chargeDistance")
        if max(abs(row_delta), abs(col_delta)) != charge_distance:
            return
        dr = 0 if row_delta == 0 else row_delta // abs(row_delta)
        dc = 0 if col_delta == 0 else col_delta // abs(col_delta)
        if (dr, dc) not in self._directions(piece):
            return

        lane = self._lane(
            state,
            move.from_row,
            move.from_col,
            dr,
            dc,
            charge_distance,
        )
        if lane is None:
            return

        targets: list[tuple[int, int, Piece]] = []
        for target_row, target_col in lane:
            target = (
                context.target_piece
                if (target_row, target_col) == (move.to_row, move.to_col)
                else state.board.grid[target_row][target_col]
            )
            if target is not None and target.piece_id != piece.piece_id:
                targets.append((target_row, target_col, target))

        if not targets:
            return

        collision = any(target.type == "elephant" for _, _, target in targets)
        for target_row, target_col, target in targets:
            if (target_row, target_col) != (move.to_row, move.to_col):
                state.board.grid[target_row][target_col] = None
            context.add_capture(
                row=target_row,
                col=target_col,
                piece=target,
                reason=(
                    "Elephant collision" if target.type == "elephant" else "Elephant charge"
                ),
            )

        if collision:
            state.board.grid[move.to_row][move.to_col] = None
            context.add_capture(
                row=move.to_row,
                col=move.to_col,
                piece=piece,
                reason="Elephant collision",
            )

        if not context.simulated:
            if collision:
                context.messages.append(
                    "Elephant charged into another Elephant; both Elephants were eliminated."
                )
            else:
                context.messages.append(
                    f"Elephant charged through {charge_distance} squares and removed "
                    f"{len(targets)} piece{'s' if len(targets) != 1 else ''}."
                )
