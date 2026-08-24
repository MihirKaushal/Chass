from __future__ import annotations

import pytest

from backend.catalog import POPULAR_PRESETS, adaptive_back_rank, catalog_payload, classic_layout


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


def test_popular_presets_do_not_duplicate_victory_modes():
    assert [mode["id"] for mode in POPULAR_PRESETS] == [
        "classic",
        "gambit",
        "draft_gambit",
    ]


def test_configured_catalog_copy_pluralizes_descriptive_counts():
    pieces = {piece["type"]: piece for piece in catalog_payload()["pieces"]}

    assert "1 clear square forward" in pieces["catapult"]["movement"]
    assert "1 occupied square" in pieces["maharani"]["movement"]
    assert "square(s)" not in pieces["catapult"]["movement"]
    assert "blocker(s)" not in " ".join(pieces["maharani"]["rules"])
