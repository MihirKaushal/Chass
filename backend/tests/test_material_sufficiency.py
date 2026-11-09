from backend.catalog import build_catalog_piece_definitions
from backend.rules.material import StartingMaterialRule

DEFINITIONS = build_catalog_piece_definitions()
KINGS = [
    {"row": 7, "col": 7, "type": "king", "color": "white"},
    {"row": 0, "col": 0, "type": "king", "color": "black"},
]


def placed(piece_type: str, color: str, row: int, col: int) -> dict:
    return {"row": row, "col": col, "type": piece_type, "color": color}


def test_checkmate_material_matches_classic_dead_positions():
    assert not StartingMaterialRule.is_sufficient("checkmate", KINGS, DEFINITIONS)
    assert not StartingMaterialRule.is_sufficient(
        "checkmate",
        [*KINGS, placed("bishop", "white", 6, 2)],
        DEFINITIONS,
    )
    assert not StartingMaterialRule.is_sufficient(
        "checkmate",
        [*KINGS, placed("knight", "white", 6, 2)],
        DEFINITIONS,
    )
    assert not StartingMaterialRule.is_sufficient(
        "checkmate",
        [
            *KINGS,
            placed("bishop", "white", 6, 2),
            placed("bishop", "black", 1, 5),
        ],
        DEFINITIONS,
    )
    assert StartingMaterialRule.is_sufficient(
        "checkmate",
        [
            *KINGS,
            placed("bishop", "white", 6, 2),
            placed("bishop", "black", 1, 4),
        ],
        DEFINITIONS,
    )
    assert StartingMaterialRule.is_sufficient(
        "checkmate",
        [*KINGS, placed("rook", "white", 6, 2)],
        DEFINITIONS,
    )


def test_victory_modes_apply_their_own_material_requirements():
    white_bishop = placed("bishop", "white", 6, 2)
    black_bishop = placed("bishop", "black", 1, 4)

    assert not StartingMaterialRule.is_sufficient(
        "check_race",
        [*KINGS, white_bishop],
        DEFINITIONS,
    )
    assert StartingMaterialRule.is_sufficient(
        "check_race",
        [*KINGS, white_bishop, black_bishop],
        DEFINITIONS,
    )
    assert not StartingMaterialRule.is_sufficient(
        "center_dominion",
        [*KINGS, white_bishop],
        DEFINITIONS,
    )
    assert StartingMaterialRule.is_sufficient(
        "center_dominion",
        [*KINGS, white_bishop, black_bishop],
        DEFINITIONS,
    )
    assert StartingMaterialRule.is_sufficient(
        "royal_center",
        [*KINGS, white_bishop],
        DEFINITIONS,
    )
    assert StartingMaterialRule.is_sufficient(
        "king_capture",
        [*KINGS, white_bishop],
        DEFINITIONS,
    )


def test_custom_piece_profiles_distinguish_attackers_from_support_pieces():
    for piece_type in ("maharani", "catapult", "elephant"):
        assert StartingMaterialRule.is_sufficient(
            "checkmate",
            [*KINGS, placed(piece_type, "white", 6, 2)],
            DEFINITIONS,
        )

    for piece_type in ("hypnotizer", "diplomat", "cannibal"):
        assert not StartingMaterialRule.is_sufficient(
            "checkmate",
            [*KINGS, placed(piece_type, "white", 6, 2)],
            DEFINITIONS,
        )

    assert StartingMaterialRule.is_sufficient(
        "checkmate",
        [
            *KINGS,
            placed("cannibal", "white", 6, 2),
            placed("cannibal", "white", 6, 3),
        ],
        DEFINITIONS,
    )


def test_gambit_configuration_requires_an_affordable_sufficient_army():
    common = {
        "victory_mode": "checkmate",
        "definitions": DEFINITIONS,
        "piece_caps": {"king": 1, "rook": 1, "bishop": 2},
        "piece_costs": {"king": 0, "rook": 5, "bishop": 3},
        "max_pieces": 3,
    }

    assert not StartingMaterialRule.can_build_sufficient_army(
        **common,
        enabled_piece_types=["king", "rook"],
        budget=4,
    )
    assert StartingMaterialRule.can_build_sufficient_army(
        **common,
        enabled_piece_types=["king", "rook"],
        budget=5,
    )
    assert StartingMaterialRule.can_build_sufficient_army(
        **common,
        enabled_piece_types=["king", "bishop"],
        budget=6,
    )


def test_gambit_feasibility_builds_material_for_both_players():
    common = {
        "definitions": DEFINITIONS,
        "enabled_piece_types": ["king", "bishop"],
        "piece_caps": {"king": 1, "bishop": 1},
        "piece_costs": {"king": 0, "bishop": 3},
        "budget": 3,
        "max_pieces": 2,
    }

    assert StartingMaterialRule.can_build_sufficient_army(
        **common,
        victory_mode="check_race",
    )
    assert StartingMaterialRule.can_build_sufficient_army(
        **common,
        victory_mode="center_dominion",
    )
