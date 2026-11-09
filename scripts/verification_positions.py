"""Deterministic positions used by engine smoke tests and benchmark reports."""

from backend.catalog import build_catalog_piece_definitions
from backend.models.schemas import CreateGameRequest
from backend.rules import RuleEngine
from backend.services.game_service import _starting_state_for_configuration_validation


def starting_state(rows=8, cols=8, configuration=None):
    engine = RuleEngine()
    request = CreateGameRequest(boardRows=rows, boardCols=cols, configuration=configuration)
    state = _starting_state_for_configuration_validation(
        request, build_catalog_piece_definitions(), engine
    )
    engine.evaluate_state(state)
    return state


def benchmark_positions():
    classic = starting_state()
    rectangular = starting_state(8, 10)
    custom = starting_state()
    custom.piece_definitions = build_catalog_piece_definitions()
    custom.configuration.enabled_piece_types = list(custom.piece_definitions)
    custom.board.grid[7][1].type = "elephant"
    custom.board.grid[0][1].type = "cannibal"
    for row, col in ((7, 1), (0, 1)):
        piece = custom.board.grid[row][col]
        definition = custom.piece_definitions[piece.type]
        piece.name, piece.points, piece.is_custom = definition.display_name, definition.points, True
        piece.custom_attributes = dict(definition.custom_attributes)
    affinity = starting_state()
    affinity.configuration.custom_rules.affinity_enabled = True
    affinity.configuration.victory.mode = "center_dominion"
    point_race = starting_state()
    point_race.configuration.victory.mode = "point_race"
    abilities = starting_state()
    abilities.configuration.special_abilities.enabled = True
    abilities.configuration.special_abilities.allowed = ["episcopal", "scorch"]
    abilities.abilities.selected = {"white": ["episcopal"], "black": ["scorch"]}
    return {
        "classic": classic,
        "rectangular": rectangular,
        "custom-pieces": custom,
        "affinity-dominion": affinity,
        "point-race": point_race,
        "abilities": abilities,
    }
