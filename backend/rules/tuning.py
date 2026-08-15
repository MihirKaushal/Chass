from __future__ import annotations

from functools import lru_cache

from backend.catalog import SPECIAL_ABILITIES, build_catalog_piece_definitions
from backend.models import GameState


@lru_cache(maxsize=1)
def _piece_defaults() -> dict[str, dict[str, int]]:
    defaults: dict[str, dict[str, int]] = {}
    for piece_type, definition in build_catalog_piece_definitions().items():
        specs = definition.custom_attributes.get("tunableParameters", [])
        defaults[piece_type] = {
            str(spec["id"]): int(spec["default"])
            for spec in specs
        }
    return defaults


@lru_cache(maxsize=1)
def _ability_defaults() -> dict[str, dict[str, int]]:
    return {
        str(ability["id"]): {
            str(spec["id"]): int(spec["default"])
            for spec in ability.get("tunableParameters", [])
        }
        for ability in SPECIAL_ABILITIES
    }


def piece_parameter(state: GameState, piece_type: str, parameter_id: str) -> int:
    configured = state.configuration.piece_parameters.get(piece_type, {})
    if parameter_id in configured:
        return int(configured[parameter_id])

    definition = state.piece_definitions.get(piece_type)
    if definition is not None:
        for parameter in definition.custom_attributes.get("configuredParameters", []):
            if parameter.get("id") == parameter_id:
                return int(parameter["value"])

    try:
        return _piece_defaults()[piece_type][parameter_id]
    except KeyError as error:
        raise KeyError(f"Unknown {piece_type} parameter: {parameter_id}") from error


def ability_parameter(state: GameState, ability_id: str, parameter_id: str) -> int:
    configured = state.configuration.special_abilities.parameters.get(ability_id, {})
    if parameter_id in configured:
        return int(configured[parameter_id])
    try:
        return _ability_defaults()[ability_id][parameter_id]
    except KeyError as error:
        raise KeyError(f"Unknown {ability_id} parameter: {parameter_id}") from error
