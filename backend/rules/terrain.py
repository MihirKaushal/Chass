from __future__ import annotations

from backend.models import BoardTerrain, GameState


def terrain_at(
    state: GameState,
    row: int,
    col: int,
    *,
    kind: str | None = None,
) -> BoardTerrain | None:
    return next(
        (
            terrain
            for terrain in state.terrain
            if terrain.row == row
            and terrain.col == col
            and (kind is None or terrain.kind == kind)
        ),
        None,
    )


def is_scorched(state: GameState, row: int, col: int) -> bool:
    return terrain_at(state, row, col, kind="scorched") is not None


def scorched_squares(state: GameState) -> set[tuple[int, int]]:
    return {
        (terrain.row, terrain.col)
        for terrain in state.terrain
        if terrain.kind == "scorched"
    }
