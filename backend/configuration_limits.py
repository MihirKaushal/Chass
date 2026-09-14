BOARD_DIMENSION_MIN = 4
BOARD_DIMENSION_MAX = 16
POINT_VALUE_MIN = 0
POINT_VALUE_MAX = 100_000
TIME_SECONDS_MIN = 30
TIME_SECONDS_MAX = 86_400
CUSTOMIZE_TIME_SECONDS_MIN = 60
TARGET_POINTS_MIN = 1
TARGET_POINTS_MAX = 100_000
DOMINION_ROUNDS_MIN = 1
DOMINION_ROUNDS_MAX = 20
CHECK_TARGET_MIN = 1
CHECK_TARGET_MAX = 100
COMMAND_POINT_CAP_MIN = 1
COMMAND_POINT_CAP_MAX = 20
AFFINITY_SQUARE_COUNT_MIN = 2
AFFINITY_SQUARE_COUNT_MAX = 32
AFFINITY_CONTROL_REQUIRED_MIN = 1
AFFINITY_CONTROL_REQUIRED_MAX = 16
ABILITY_SELECTION_MIN = 1
ABILITY_SELECTION_MAX = 16
BARRICADE_COUNT_MIN = 0
BARRICADE_COUNT_MAX = 8
GAMBIT_BUDGET_MIN = 0
GAMBIT_BUDGET_MAX = 100_000
GAMBIT_MAX_PIECES_MIN = 1
GAMBIT_MAX_PIECES_MAX = 128
GAMBIT_SETUP_ROWS_MIN = 1
GAMBIT_SETUP_ROWS_MAX = 8
GAMBIT_MAX_QUEENS_MIN = 0
GAMBIT_MAX_QUEENS_MAX = GAMBIT_MAX_PIECES_MAX - 1
GAMBIT_PIECE_CAP_MIN = 0
DRAFT_POOL_COUNT_MIN = 0
DRAFT_POOL_COUNT_MAX = 256

GAMBIT_DEFAULT_PAWN_CAP = 15
GAMBIT_DEFAULT_QUEEN_CAP = 2
GAMBIT_DEFAULT_OTHER_PIECE_CAP = 3


def default_gambit_piece_cap(piece_type: str, max_pieces: int = 16) -> int:
    """Return the bounded default army limit for a Gambit piece type."""
    if piece_type == "king":
        return 1
    if piece_type == "barricade":
        return 0

    preferred = (
        GAMBIT_DEFAULT_PAWN_CAP
        if piece_type == "pawn"
        else GAMBIT_DEFAULT_QUEEN_CAP
        if piece_type == "queen"
        else GAMBIT_DEFAULT_OTHER_PIECE_CAP
    )
    return min(preferred, max(0, max_pieces - 1))


def customization_limits() -> dict[str, int]:
    return {
        "boardMin": BOARD_DIMENSION_MIN,
        "boardMax": BOARD_DIMENSION_MAX,
        "pointMin": POINT_VALUE_MIN,
        "pointMax": POINT_VALUE_MAX,
        "timeSecondsMin": CUSTOMIZE_TIME_SECONDS_MIN,
        "timeSecondsMax": TIME_SECONDS_MAX,
        "targetPointsMin": TARGET_POINTS_MIN,
        "targetPointsMax": TARGET_POINTS_MAX,
        "dominionRoundsMin": DOMINION_ROUNDS_MIN,
        "dominionRoundsMax": DOMINION_ROUNDS_MAX,
        "checkTargetMin": CHECK_TARGET_MIN,
        "checkTargetMax": CHECK_TARGET_MAX,
        "commandPointCapMin": COMMAND_POINT_CAP_MIN,
        "commandPointCapMax": COMMAND_POINT_CAP_MAX,
        "affinitySquareCountMin": AFFINITY_SQUARE_COUNT_MIN,
        "affinitySquareCountMax": AFFINITY_SQUARE_COUNT_MAX,
        "affinityControlRequiredMin": AFFINITY_CONTROL_REQUIRED_MIN,
        "affinityControlRequiredMax": AFFINITY_CONTROL_REQUIRED_MAX,
        "abilitySelectionMin": ABILITY_SELECTION_MIN,
        "abilitySelectionMax": ABILITY_SELECTION_MAX,
        "barricadeCountMin": BARRICADE_COUNT_MIN,
        "barricadeCountMax": BARRICADE_COUNT_MAX,
        "gambitBudgetMin": GAMBIT_BUDGET_MIN,
        "gambitBudgetMax": GAMBIT_BUDGET_MAX,
        "gambitMaxPiecesMin": GAMBIT_MAX_PIECES_MIN,
        "gambitMaxPiecesMax": GAMBIT_MAX_PIECES_MAX,
        "gambitSetupRowsMin": GAMBIT_SETUP_ROWS_MIN,
        "gambitSetupRowsMax": GAMBIT_SETUP_ROWS_MAX,
        "gambitMaxQueensMin": GAMBIT_MAX_QUEENS_MIN,
        "gambitMaxQueensMax": GAMBIT_MAX_QUEENS_MAX,
        "pieceCapMin": GAMBIT_PIECE_CAP_MIN,
        "draftPoolCountMin": DRAFT_POOL_COUNT_MIN,
        "draftPoolCountMax": DRAFT_POOL_COUNT_MAX,
    }
