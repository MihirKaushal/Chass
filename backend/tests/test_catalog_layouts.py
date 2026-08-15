from __future__ import annotations

import pytest

from backend.catalog import POPULAR_PRESETS, adaptive_back_rank, classic_layout


@pytest.mark.parametrize("cols", range(4, 17))
def test_classic_layout_adapts_armies_to_board_width(cols: int):
    rows = 6
    layout = classic_layout(rows, cols)
    occupied = {(piece["row"], piece["col"]) for piece in layout}

    expected_back_rank_size = min(cols, 8)
    assert len(layout) == expected_back_rank_size * 4
    assert len(occupied) == len(layout)
    assert sum(piece["type"] == "king" for piece in layout) == 2
    assert all(0 <= piece["row"] < rows for piece in layout)
    assert all(0 <= piece["col"] < cols for piece in layout)


@pytest.mark.parametrize(
    ("cols", "expected"),
    [
        (4, ["rook", "queen", "king", "rook"]),
        (5, ["rook", "knight", "king", "knight", "rook"]),
        (6, ["rook", "knight", "queen", "king", "knight", "rook"]),
        (
            7,
            ["rook", "knight", "bishop", "king", "bishop", "knight", "rook"],
        ),
    ],
)
def test_adaptive_back_rank_keeps_one_king(cols: int, expected: list[str]):
    assert adaptive_back_rank(cols) == expected


def test_king_hunt_copy_matches_capture_rules():
    king_hunt = next(mode for mode in POPULAR_PRESETS if mode["id"] == "king_hunt")
    assert king_hunt["summary"] == (
        "Check restrictions are disabled; capture the opposing King to win."
    )
