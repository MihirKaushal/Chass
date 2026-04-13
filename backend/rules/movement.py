from __future__ import annotations

from math import gcd

from backend.models import GameState, MoveOption


def in_bounds(size: int, row: int, col: int) -> bool:
    return 0 <= row < size and 0 <= col < size


def _normalize_for_color(delta: int, color: str, relative_to_color: bool) -> int:
    if not relative_to_color:
        return delta
    return delta if color == "white" else -delta


def _path_is_clear(
    state: GameState,
    from_row: int,
    from_col: int,
    to_row: int,
    to_col: int,
) -> bool:
    dr = to_row - from_row
    dc = to_col - from_col

    if dr == 0 and dc == 0:
        return False

    step_count = gcd(abs(dr), abs(dc))
    if step_count <= 1:
        return True

    step_row = dr // step_count
    step_col = dc // step_count

    current_row = from_row + step_row
    current_col = from_col + step_col

    while current_row != to_row or current_col != to_col:
        if state.board.grid[current_row][current_col] is not None:
            return False
        current_row += step_row
        current_col += step_col

    return True


def generate_piece_moves(state: GameState, row: int, col: int) -> list[MoveOption]:
    if not in_bounds(state.board.size, row, col):
        return []

    piece = state.board.grid[row][col]
    if piece is None:
        return []

    definition = state.piece_definitions.get(piece.type)
    if definition is None:
        return []

    move_options: list[MoveOption] = []

    for pattern in definition.patterns:
        if pattern.requires_unmoved and piece.has_moved:
            continue

        step = 1
        while True:
            raw_dr = pattern.dr * step
            raw_dc = pattern.dc * step
            dr = _normalize_for_color(raw_dr, piece.color, pattern.relative_to_color)
            dc = raw_dc

            target_row = row + dr
            target_col = col + dc

            if not in_bounds(state.board.size, target_row, target_col):
                break

            target_piece = state.board.grid[target_row][target_col]
            path_clear = (
                True
                if not pattern.requires_clear_path
                else _path_is_clear(state, row, col, target_row, target_col)
            )

            if target_piece is None:
                if pattern.mode in ("move", "both") and path_clear:
                    move_options.append(
                        MoveOption(
                            from_row=row,
                            from_col=col,
                            to_row=target_row,
                            to_col=target_col,
                            captures=[],
                            explanation=f"{definition.display_name} movement pattern",
                        )
                    )
            else:
                if (
                    target_piece.color != piece.color
                    and pattern.mode in ("capture", "both")
                    and path_clear
                ):
                    move_options.append(
                        MoveOption(
                            from_row=row,
                            from_col=col,
                            to_row=target_row,
                            to_col=target_col,
                            captures=[
                                {
                                    "row": target_row,
                                    "col": target_col,
                                    "piece": target_piece,
                                }
                            ],
                            explanation=f"{definition.display_name} capture pattern",
                        )
                    )
                # pieces block further travel for this pattern branch.
                break

            if not pattern.repeat:
                break
            step += 1

    deduped: dict[tuple[int, int], MoveOption] = {}
    for option in move_options:
        deduped[(option.to_row, option.to_col)] = option

    return list(deduped.values())
