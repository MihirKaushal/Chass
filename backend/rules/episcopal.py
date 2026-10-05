from __future__ import annotations

from dataclasses import dataclass

from backend.models import GameState, Piece
from backend.rules.terrain import is_scorched


@dataclass(frozen=True)
class EpiscopalDestination:
    row: int
    col: int
    captured_piece: Piece | None = None


def _runtime_active(state: GameState, piece: Piece, key: str) -> bool:
    if piece.color not in {"white", "black"}:
        return False
    try:
        active_until = int(piece.runtime.get(key, 0))
    except (TypeError, ValueError):
        return False
    return active_until > state.turn_counts[piece.color]


def _can_capture(state: GameState, bishop: Piece, target: Piece) -> bool:
    return (
        target.color in {"white", "black"}
        and target.color != bishop.color
        and target.type not in {"king", "barricade", "diplomat"}
        and not _runtime_active(state, target, "capture_immune_until_turn")
    )


def episcopal_destinations(
    state: GameState,
    row: int,
    col: int,
) -> list[EpiscopalDestination]:
    """Return same-color orthogonal Bishop jumps allowed by Episcopal."""
    bishop = state.board.grid[row][col]
    if bishop is None or bishop.type != "bishop" or bishop.color == "neutral":
        return []
    if _runtime_active(state, bishop, "pacified_until_turn"):
        return []

    origin_color = (row + col) % 2
    destinations: list[EpiscopalDestination] = []
    for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        distance = 1
        while True:
            target_row = row + (delta_row * distance)
            target_col = col + (delta_col * distance)
            if not (
                0 <= target_row < state.board.rows
                and 0 <= target_col < state.board.cols
            ):
                break

            target = state.board.grid[target_row][target_col]
            if target is not None and target.type == "barricade":
                break

            same_square_color = (target_row + target_col) % 2 == origin_color
            if same_square_color and not is_scorched(state, target_row, target_col):
                if target is None:
                    destinations.append(EpiscopalDestination(target_row, target_col))
                elif _can_capture(state, bishop, target):
                    destinations.append(
                        EpiscopalDestination(target_row, target_col, target)
                    )

            # Ordinary pieces and scorched terrain may be jumped. Only a
            # Barricade blocks the lane, as handled above.
            distance += 1

    return destinations
