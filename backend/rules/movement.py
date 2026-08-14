from __future__ import annotations

from math import gcd

from backend.models import GameState, MoveOption, MovePattern, Piece


def in_bounds(rows: int, cols: int, row: int, col: int) -> bool:
    return 0 <= row < rows and 0 <= col < cols


def _normalize_for_color(delta: int, color: str, relative_to_color: bool) -> int:
    if not relative_to_color:
        return delta
    return delta if color == "white" else -delta


def _runtime_active(state: GameState, piece: Piece, key: str) -> bool:
    if piece.color not in {"white", "black"}:
        return False
    try:
        until_turn = int(piece.runtime.get(key, 0))
    except (TypeError, ValueError):
        return False
    return until_turn > state.turn_counts[piece.color]


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


def _jump_crosses_barricade(
    state: GameState,
    from_row: int,
    from_col: int,
    to_row: int,
    to_col: int,
) -> bool:
    row_min, row_max = sorted((from_row, to_row))
    col_min, col_max = sorted((from_col, to_col))
    for row in range(row_min, row_max + 1):
        for col in range(col_min, col_max + 1):
            if (row, col) in {(from_row, from_col), (to_row, to_col)}:
                continue
            piece = state.board.grid[row][col]
            if piece is not None and piece.type == "barricade":
                return True
    return False


def _can_capture(state: GameState, attacker: Piece, target: Piece) -> bool:
    if target.color == attacker.color:
        return False
    if target.type in {"barricade", "diplomat"}:
        return False
    return not _runtime_active(state, target, "capture_immune_until_turn")


def _option(
    state: GameState,
    piece: Piece,
    row: int,
    col: int,
    target_row: int,
    target_col: int,
    explanation: str,
) -> MoveOption | None:
    target = state.board.grid[target_row][target_col]
    captures = []
    if target is not None:
        if not _can_capture(state, piece, target):
            return None
        captures = [{"row": target_row, "col": target_col, "piece": target}]
    return MoveOption(
        from_row=row,
        from_col=col,
        to_row=target_row,
        to_col=target_col,
        captures=captures,
        explanation=explanation,
    )


def _patterns_for_piece(state: GameState, piece: Piece) -> list[MovePattern]:
    definition = state.piece_definitions.get(piece.type)
    if definition is None:
        return []
    patterns = list(definition.patterns)
    if piece.type == "king" and _runtime_active(state, piece, "love_until_turn"):
        patterns.extend(
            MovePattern(dr=dr, dc=dc, repeat=True, requires_clear_path=True)
            for dr, dc in (
                (-1, -1),
                (-1, 0),
                (-1, 1),
                (0, -1),
                (0, 1),
                (1, -1),
                (1, 0),
                (1, 1),
            )
        )
    return patterns


def _maharani_jump_moves(
    state: GameState,
    row: int,
    col: int,
    piece: Piece,
) -> list[MoveOption]:
    moves: list[MoveOption] = []
    for step_row, step_col in (
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    ):
        crossed_piece = False
        distance = 1
        while True:
            target_row = row + step_row * distance
            target_col = col + step_col * distance
            if not in_bounds(state.board.rows, state.board.cols, target_row, target_col):
                break
            target = state.board.grid[target_row][target_col]
            if target is not None and target.type == "barricade":
                break
            if not crossed_piece:
                if target is not None:
                    crossed_piece = True
                distance += 1
                continue
            option = _option(
                state,
                piece,
                row,
                col,
                target_row,
                target_col,
                "Maharani crossed one occupied square",
            )
            if option is not None:
                moves.append(option)
            if target is not None:
                break
            distance += 1
    return moves


def _maharani_jump_attacks(
    state: GameState,
    row: int,
    col: int,
) -> set[tuple[int, int]]:
    attacks: set[tuple[int, int]] = set()
    for step_row, step_col in (
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    ):
        crossed_piece = False
        distance = 1
        while True:
            target_row = row + step_row * distance
            target_col = col + step_col * distance
            if not in_bounds(state.board.rows, state.board.cols, target_row, target_col):
                break
            target = state.board.grid[target_row][target_col]
            if target is not None and target.type == "barricade":
                break
            if not crossed_piece:
                if target is not None:
                    crossed_piece = True
                distance += 1
                continue
            if target is None or target.type != "diplomat":
                attacks.add((target_row, target_col))
            if target is not None:
                break
            distance += 1
    return attacks


def _cannibal_can_consume(state: GameState, target: Piece) -> bool:
    if target.type in {"barricade", "diplomat"}:
        return False
    return not _runtime_active(state, target, "capture_immune_until_turn")


def _cannibal_powered_moves(
    state: GameState,
    row: int,
    col: int,
    piece: Piece,
) -> list[MoveOption]:
    inherited_type = str(piece.runtime.get("cannibal_form", ""))
    if not inherited_type or inherited_type == "cannibal":
        inherited_type = "queen"
    definition = state.piece_definitions.get(inherited_type)
    if definition is None:
        return []

    proxy = piece.model_copy(deep=True)
    proxy.type = inherited_type
    proxy.name = definition.display_name
    proxy.has_moved = True
    proxy.runtime = {}
    state.board.grid[row][col] = proxy
    try:
        inherited = generate_piece_moves(state, row, col)
    finally:
        state.board.grid[row][col] = piece

    return [
        MoveOption(
            from_row=row,
            from_col=col,
            to_row=option.to_row,
            to_col=option.to_col,
            explanation=f"Cannibal using {definition.display_name} mobility",
        )
        for option in inherited
        if state.board.grid[option.to_row][option.to_col] is None
    ]


def _cannibal_moves(
    state: GameState,
    row: int,
    col: int,
    piece: Piece,
) -> list[MoveOption]:
    if int(piece.runtime.get("cannibal_moves_remaining", 0)) > 0:
        return _cannibal_powered_moves(state, row, col, piece)

    moves: list[MoveOption] = []
    backward = 1 if piece.color == "white" else -1
    edible_squares = {(row + backward, col + dc) for dc in (-1, 0, 1)}
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            target_row, target_col = row + dr, col + dc
            if not in_bounds(
                state.board.rows,
                state.board.cols,
                target_row,
                target_col,
            ):
                continue
            target = state.board.grid[target_row][target_col]
            if target is None:
                moves.append(
                    MoveOption(
                        from_row=row,
                        from_col=col,
                        to_row=target_row,
                        to_col=target_col,
                        explanation="Cannibal movement",
                    )
                )
            elif (
                (target_row, target_col) in edible_squares
                and _cannibal_can_consume(state, target)
            ):
                moves.append(
                    MoveOption(
                        from_row=row,
                        from_col=col,
                        to_row=target_row,
                        to_col=target_col,
                        captures=[{"row": target_row, "col": target_col, "piece": target}],
                        explanation=f"Cannibal consumes {target.name}",
                    )
                )
    return moves


def _cannibal_attacks(
    state: GameState,
    row: int,
    col: int,
    piece: Piece,
) -> set[tuple[int, int]]:
    if int(piece.runtime.get("cannibal_moves_remaining", 0)) > 0:
        return set()
    backward = 1 if piece.color == "white" else -1
    attacks: set[tuple[int, int]] = set()
    for dc in (-1, 0, 1):
        target_row, target_col = row + backward, col + dc
        if not in_bounds(state.board.rows, state.board.cols, target_row, target_col):
            continue
        target = state.board.grid[target_row][target_col]
        if target is None or _cannibal_can_consume(state, target):
            attacks.add((target_row, target_col))
    return attacks


def generate_piece_moves(state: GameState, row: int, col: int) -> list[MoveOption]:
    if not in_bounds(state.board.rows, state.board.cols, row, col):
        return []

    piece = state.board.grid[row][col]
    if piece is None or piece.color == "neutral":
        return []
    if _runtime_active(state, piece, "pacified_until_turn"):
        return []
    if piece.type == "catapult" and _runtime_active(
        state, piece, "catapult_ready_turn"
    ):
        return []

    definition = state.piece_definitions.get(piece.type)
    if definition is None:
        return []
    if piece.type == "cannibal":
        return _cannibal_moves(state, row, col, piece)

    move_options: list[MoveOption] = []
    for pattern in _patterns_for_piece(state, piece):
        if pattern.requires_unmoved and piece.has_moved:
            continue

        step = 1
        while True:
            raw_dr = pattern.dr * step
            raw_dc = pattern.dc * step
            dr = _normalize_for_color(raw_dr, piece.color, pattern.relative_to_color)
            target_row = row + dr
            target_col = col + raw_dc
            if not in_bounds(state.board.rows, state.board.cols, target_row, target_col):
                break

            target_piece = state.board.grid[target_row][target_col]
            path_clear = not pattern.requires_clear_path or _path_is_clear(
                state, row, col, target_row, target_col
            )
            is_knight_jump = abs(target_row - row) * abs(target_col - col) == 2
            if is_knight_jump and _jump_crosses_barricade(
                state, row, col, target_row, target_col
            ):
                path_clear = False

            if target_piece is None:
                if pattern.mode in ("move", "both") and path_clear:
                    move_options.append(
                        MoveOption(
                            from_row=row,
                            from_col=col,
                            to_row=target_row,
                            to_col=target_col,
                            explanation=f"{definition.display_name} movement",
                        )
                    )
            else:
                if (
                    pattern.mode in ("capture", "both")
                    and path_clear
                    and _can_capture(state, piece, target_piece)
                ):
                    move_options.append(
                        MoveOption(
                            from_row=row,
                            from_col=col,
                            to_row=target_row,
                            to_col=target_col,
                            captures=[
                                {"row": target_row, "col": target_col, "piece": target_piece}
                            ],
                            explanation=f"{definition.display_name} capture",
                        )
                    )
                break

            if not pattern.repeat:
                break
            step += 1

    if piece.type == "maharani":
        move_options.extend(_maharani_jump_moves(state, row, col, piece))

    deduped: dict[tuple[int, int], MoveOption] = {}
    for option in move_options:
        deduped[(option.to_row, option.to_col)] = option
    return list(deduped.values())


def _pattern_attack_squares(
    state: GameState,
    row: int,
    col: int,
    piece: Piece,
) -> set[tuple[int, int]]:
    attacks: set[tuple[int, int]] = set()
    for pattern in _patterns_for_piece(state, piece):
        if pattern.mode not in {"capture", "both"}:
            continue
        if pattern.requires_unmoved and piece.has_moved:
            continue
        step = 1
        while True:
            dr = _normalize_for_color(
                pattern.dr * step,
                piece.color,
                pattern.relative_to_color,
            )
            dc = pattern.dc * step
            target_row = row + dr
            target_col = col + dc
            if not in_bounds(state.board.rows, state.board.cols, target_row, target_col):
                break
            is_knight_jump = abs(target_row - row) * abs(target_col - col) == 2
            if is_knight_jump and _jump_crosses_barricade(
                state, row, col, target_row, target_col
            ):
                break
            target = state.board.grid[target_row][target_col]
            if target is not None and target.type in {"barricade", "diplomat"}:
                break
            attacks.add((target_row, target_col))
            if target is not None or not pattern.repeat:
                break
            step += 1
    return attacks


def generate_piece_attacks(state: GameState, row: int, col: int) -> set[tuple[int, int]]:
    if not in_bounds(state.board.rows, state.board.cols, row, col):
        return set()
    piece = state.board.grid[row][col]
    if piece is None or piece.color == "neutral":
        return set()
    if _runtime_active(state, piece, "pacified_until_turn"):
        return set()
    if piece.type == "catapult" and _runtime_active(
        state, piece, "catapult_ready_turn"
    ):
        return set()
    if piece.type in {"barricade", "hypnotizer", "diplomat"}:
        return set()
    if piece.type == "cannibal":
        return _cannibal_attacks(state, row, col, piece)

    attacks = _pattern_attack_squares(state, row, col, piece)
    if piece.type == "maharani":
        attacks.update(_maharani_jump_attacks(state, row, col))

    if piece.type == "catapult" and not _runtime_active(
        state, piece, "catapult_ready_turn"
    ):
        direction = -1 if piece.color == "white" else 1
        for dc in (-1, 0, 1):
            for distance in (2, 3):
                target_row = row + direction * distance
                target_col = col + dc * distance
                if not in_bounds(
                    state.board.rows, state.board.cols, target_row, target_col
                ):
                    continue
                blocked = False
                for step in range(1, distance):
                    check_row = row + direction * step
                    check_col = col + dc * step
                    blocker = state.board.grid[check_row][check_col]
                    if blocker is not None and blocker.type == "barricade":
                        blocked = True
                        break
                if not blocked:
                    attacks.add((target_row, target_col))

    selected = state.abilities.selected.get(piece.color, []) if piece.color != "neutral" else []
    if piece.type == "bishop" and "episcopal" in selected:
        ready_turn = int(state.abilities.runtime[piece.color].get("episcopal_ready_turn", 0))
        if state.turn_counts[piece.color] >= ready_turn:
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                target_row, target_col = row + dr, col + dc
                if in_bounds(state.board.rows, state.board.cols, target_row, target_col):
                    target = state.board.grid[target_row][target_col]
                    if target is None or target.type not in {"barricade", "diplomat"}:
                        attacks.add((target_row, target_col))
    return attacks
