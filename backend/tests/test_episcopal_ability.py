from __future__ import annotations

from backend.catalog import (
    build_catalog_piece_definitions,
    normalize_ability_parameters,
)
from backend.models import BoardTerrain, Piece
from backend.routes.game import game_service
from backend.rules.episcopal import episcopal_destinations
from backend.rules.movement import generate_piece_attacks


def _piece(state, piece_type: str, color: str) -> Piece:
    definition = state.piece_definitions[piece_type]
    return Piece(
        type=piece_type,
        name=definition.display_name,
        color=color,
        points=definition.points,
        is_custom=definition.is_custom,
        custom_attributes=dict(definition.custom_attributes),
    )


def _empty_state(client):
    created = client.post("/game/create", json={"mode": "local"}).json()["game"]
    state = game_service.repository.get_game(created["id"]).state.clone()
    state.piece_definitions = build_catalog_piece_definitions()
    state.board.grid = [
        [None for _ in range(state.board.cols)]
        for _ in range(state.board.rows)
    ]
    state.terrain = []
    state.turn_counts = {"white": 5, "black": 5}
    return state


def test_episcopal_jumps_pieces_and_scorch_but_respects_target_exclusions(client):
    state = _empty_state(client)
    bishop = _piece(state, "bishop", "white")
    state.board.grid[6][2] = bishop
    state.board.grid[4][2] = None
    state.terrain.append(BoardTerrain(kind="scorched", row=4, col=2))
    state.board.grid[2][2] = _piece(state, "rook", "black")
    state.board.grid[0][2] = _piece(state, "king", "black")
    state.board.grid[6][4] = _piece(state, "pawn", "white")
    state.board.grid[6][6] = _piece(state, "queen", "black")
    protected = _piece(state, "knight", "black")
    protected.runtime["capture_immune_until_turn"] = 8
    state.board.grid[6][0] = protected

    destinations = {
        (destination.row, destination.col): destination
        for destination in episcopal_destinations(state, 6, 2)
    }

    assert (2, 2) in destinations
    assert destinations[(2, 2)].captured_piece.type == "rook"
    assert (6, 6) in destinations
    assert destinations[(6, 6)].captured_piece.type == "queen"
    assert (4, 2) not in destinations  # Scorched destinations stay impassable.
    assert (0, 2) not in destinations  # Episcopal never targets a King.
    assert (6, 4) not in destinations  # Allied pieces may be jumped, not captured.
    assert (6, 0) not in destinations  # Capture immunity remains authoritative.
    assert (0, 2) not in generate_piece_attacks(state, 6, 2)


def test_episcopal_barricade_blocks_every_destination_beyond_it(client):
    state = _empty_state(client)
    state.board.grid[6][2] = _piece(state, "bishop", "white")
    state.board.grid[6][5] = _piece(state, "barricade", "neutral")
    state.board.grid[6][6] = _piece(state, "queen", "black")

    targets = {
        (destination.row, destination.col)
        for destination in episcopal_destinations(state, 6, 2)
    }

    assert (6, 4) in targets
    assert (6, 6) not in targets


def test_episcopal_ignores_the_retired_shift_distance_from_cached_clients():
    configured = normalize_ability_parameters(
        {"episcopal": {"cooldownTurns": 10, "shiftDistance": 3}}
    )

    assert configured["episcopal"] == {"cooldownTurns": 10}
