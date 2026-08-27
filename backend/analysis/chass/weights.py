from __future__ import annotations

MODEL_VERSION = "chass-hce-v1"
ENGINE_VERSION = "Chass Engine 0.1 HCE"

FACTOR_ORDER = (
    "goal_progress",
    "material",
    "king_safety",
    "tactical_pressure",
    "piece_activity",
    "center_control",
    "special_resources",
    "pawn_structure",
    "terrain",
    "tempo",
)

BASE_FACTOR_WEIGHTS = {
    "goal_progress": 3.0,
    "material": 1.0,
    "king_safety": 1.2,
    "tactical_pressure": 1.0,
    "piece_activity": 0.55,
    "center_control": 0.4,
    "special_resources": 0.65,
    "pawn_structure": 0.25,
    "terrain": 0.25,
    "tempo": 0.1,
}

VICTORY_WEIGHT_OVERRIDES = {
    "checkmate": {
        "goal_progress": 2.2,
        "king_safety": 1.6,
        "tactical_pressure": 1.2,
    },
    "king_capture": {
        "goal_progress": 3.8,
        "king_safety": 1.8,
        "tactical_pressure": 1.3,
    },
    "timed": {
        "goal_progress": 3.4,
        "king_safety": 1.5,
        "special_resources": 0.9,
    },
    "point_race": {
        "goal_progress": 5.0,
        "material": 0.55,
        "king_safety": 0.15,
        "tactical_pressure": 1.35,
        "special_resources": 1.0,
    },
    "elimination": {
        "goal_progress": 4.4,
        "material": 1.35,
        "king_safety": 0.35,
        "tactical_pressure": 1.3,
    },
    "royal_score": {
        "goal_progress": 4.7,
        "material": 0.65,
        "king_safety": 1.45,
        "tactical_pressure": 1.2,
    },
    "center_dominion": {
        "goal_progress": 5.0,
        "center_control": 2.2,
        "piece_activity": 0.75,
        "king_safety": 1.1,
    },
    "royal_center": {
        "goal_progress": 5.2,
        "center_control": 1.5,
        "king_safety": 1.35,
        "piece_activity": 0.7,
    },
    "check_race": {
        "goal_progress": 5.0,
        "king_safety": 1.45,
        "tactical_pressure": 1.55,
    },
}

CLASSIC_INTRINSIC_VALUES = {
    "pawn": 1.0,
    "knight": 3.0,
    "bishop": 3.2,
    "rook": 5.0,
    "queen": 9.0,
    "king": 0.0,
}

PIECE_PARAMETER_COVERAGE = {
    "maharani": frozenset({"blockersCrossed"}),
    "catapult": frozenset(
        {
            "movementDistance",
            "shortProjectileSkip",
            "shortRecoveryTurns",
            "longProjectileSkip",
            "longRecoveryTurns",
        }
    ),
    "barricade": frozenset({"movementDistance", "controlRange"}),
    "hypnotizer": frozenset(
        {
            "movementDistance",
            "weakContactTurns",
            "mediumContactTurns",
            "strongContactTurns",
        }
    ),
    "diplomat": frozenset(
        {
            "movementDistance",
            "contactTurns",
            "pacifiedTurns",
            "retireAfterPacifications",
        }
    ),
    "cannibal": frozenset(
        {"movementDistance", "consumeDistance", "borrowedMovementMoves"}
    ),
    "elephant": frozenset(
        {"movementDistance", "chargeDistance", "alliedChargeLimit"}
    ),
}

ABILITY_PARAMETER_COVERAGE = {
    "necromancy": frozenset({"cooldownTurns"}),
    "getaway": frozenset({"usesPerGame"}),
    "eye_for_an_eye": frozenset({"cooldownTurns"}),
    "kamikaze": frozenset({"blastRadius"}),
    "episcopal": frozenset({"cooldownTurns", "shiftDistance"}),
    "power_of_love": frozenset({"durationTurns"}),
    "scorch": frozenset({"cooldownTurns", "usesPerGame", "minimumGap"}),
}

VICTORY_MODE_COVERAGE = frozenset(VICTORY_WEIGHT_OVERRIDES)

RULE_EVALUATION_COVERAGE = {
    "bounds": "authoritative action generation",
    "piece_presence": "authoritative action generation",
    "turn_order": "authoritative action generation",
    "movement_patterns": "mobility and tactical pressure",
    "castling": "mobility and King safety",
    "en_passant": "tactical pressure",
    "elephant_charge": "Elephant utility and tactical pressure",
    "check": "King safety and tactical pressure",
    "capture": "material and tactical pressure",
    "cannibal_consumption": "Cannibal utility and tactical pressure",
    "promotion": "Pawn structure and tactical pressure",
    "score": "goal progress and special resources",
    "center_dominion": "goal progress and center control",
    "royal_center": "goal progress and center control",
    "check_race": "goal progress and tactical pressure",
    "checkmate": "terminal search and King safety",
    "configured_victory": "goal progress and terminal search",
    "classic_draws": "terminal search",
    "stalemate": "terminal search",
    "double_capture_rook": "Rook utility and tactical pressure",
    "score_target_win": "goal progress and score pressure",
}
