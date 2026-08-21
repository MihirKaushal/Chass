from __future__ import annotations

from backend.catalog import default_scorch_uses

CLASSIC_TYPES = ["pawn", "knight", "bishop", "rook", "queen", "king"]


def scorch_game(
    placements: list[dict],
    *,
    rows: int = 8,
    cols: int = 8,
    parameters: dict[str, int] | None = None,
) -> dict:
    ability = {
        "enabled": True,
        "allowed": ["scorch"],
    }
    if parameters is not None:
        ability["parameters"] = {"scorch": parameters}
    return {
        "mode": "local",
        "boardRows": rows,
        "boardCols": cols,
        "configuration": {
            "schemaVersion": 2,
            "presetId": "scorch-test",
            "formationId": "custom",
            "enabledPieces": CLASSIC_TYPES,
            "piecePoints": {"king": 0, "rook": 5, "knight": 3},
            "initialLayout": placements,
            "victory": {"mode": "checkmate"},
            "specialAbilities": ability,
            "gambit": {"enabled": False},
        },
    }


def start_scorch_game(client, payload: dict) -> dict:
    created = client.post("/game/create", json=payload)
    assert created.status_code == 200, created.text
    game = created.json()["game"]
    white = client.post(
        f"/game/{game['id']}/ability",
        json={"abilityId": "scorch", "expectedVersion": game["version"]},
    ).json()
    handoff = client.post(
        f"/game/{game['id']}/setup/handoff",
        json={"expectedVersion": white["version"]},
    ).json()
    black = client.post(
        f"/game/{game['id']}/ability",
        json={"abilityId": "scorch", "expectedVersion": handoff["version"]},
    )
    assert black.status_code == 200, black.text
    return black.json()


def use_scorch(client, game: dict, row: int, col: int):
    return client.post(
        f"/game/{game['id']}/action",
        json={
            "actionType": "scorch",
            "target": {"row": row, "col": col},
            "expectedVersion": game["version"],
        },
    )


def scorch_targets(game: dict) -> set[tuple[int, int]]:
    return {
        (action["target"]["row"], action["target"]["col"])
        for action in game["availableActions"]
        if action["actionType"] == "scorch"
    }


def move_targets(game: dict, row: int, col: int) -> set[tuple[int, int]]:
    return {
        (move["to"]["row"], move["to"]["col"])
        for move in game["validMoves"]
        if move["from"] == {"row": row, "col": col}
    }


def base_layout(rows: int = 8, cols: int = 8) -> list[dict]:
    return [
        {"row": rows - 1, "col": cols - 1, "type": "king", "color": "white"},
        {"row": 0, "col": cols - 1, "type": "king", "color": "black"},
        {"row": rows - 1, "col": 0, "type": "rook", "color": "white"},
    ]


def test_scorch_catalog_and_board_area_default(client):
    assert default_scorch_uses(8, 8) == 2
    assert default_scorch_uses(10, 10) == 3
    assert default_scorch_uses(16, 16) == 4

    catalog = client.get("/game/catalog").json()
    scorch = next(
        ability
        for ability in catalog["specialAbilities"]
        if ability["id"] == "scorch"
    )
    specs = {parameter["id"]: parameter for parameter in scorch["tunableParameters"]}
    assert specs["cooldownTurns"]["default"] == 10
    assert specs["usesPerGame"]["dynamicDefault"] == "board_sqrt_quarter"
    assert specs["minimumGap"]["default"] == 1

    game = start_scorch_game(
        client,
        scorch_game(base_layout(10, 10), rows=10, cols=10),
    )
    assert game["configuration"]["specialAbilities"]["parameters"]["scorch"][
        "usesPerGame"
    ] == 3


def test_scorch_persists_terrain_starts_cooldown_and_enforces_gap(client):
    game = start_scorch_game(client, scorch_game(base_layout()))
    assert (3, 3) in scorch_targets(game)
    assert (7, 7) not in scorch_targets(game)

    scorched = use_scorch(client, game, 3, 3)
    assert scorched.status_code == 200, scorched.text
    result = scorched.json()
    assert result["terrain"][0] | {"terrainId": result["terrain"][0]["terrainId"]} == {
        "terrainId": result["terrain"][0]["terrainId"],
        "kind": "scorched",
        "row": 3,
        "col": 3,
        "owner": "white",
        "metadata": {},
    }
    assert result["abilities"]["usageCount"]["white"]["scorch"] == 1
    assert result["abilities"]["cooldowns"]["white"]["scorch"] == 10
    assert result["history"][-1]["actionType"] == "scorch"
    assert (2, 2) not in scorch_targets(result)
    assert (2, 3) not in scorch_targets(result)
    assert (3, 4) not in scorch_targets(result)
    assert (5, 5) in scorch_targets(result)


def test_scorch_editable_gap_and_usage_limit(client):
    parameters = {"cooldownTurns": 0, "usesPerGame": 1, "minimumGap": 0}
    game = start_scorch_game(
        client,
        scorch_game(base_layout(), parameters=parameters),
    )
    white = use_scorch(client, game, 3, 3).json()
    assert (3, 4) in scorch_targets(white)

    black = use_scorch(client, white, 3, 4)
    assert black.status_code == 200, black.text
    result = black.json()
    assert result["currentPlayer"] == "white"
    assert not scorch_targets(result)


def test_scorch_blocks_sliding_moves_but_not_jumps(client):
    rook_game = start_scorch_game(
        client,
        scorch_game(
            [
                {"row": 7, "col": 0, "type": "king", "color": "white"},
                {"row": 0, "col": 7, "type": "king", "color": "black"},
                {"row": 4, "col": 7, "type": "rook", "color": "black"},
            ]
        ),
    )
    rook_game = use_scorch(client, rook_game, 4, 4).json()
    rook_moves = move_targets(rook_game, 4, 7)
    assert {(4, 6), (4, 5)} <= rook_moves
    assert (4, 4) not in rook_moves
    assert (4, 3) not in rook_moves

    knight_game = start_scorch_game(
        client,
        scorch_game(
            [
                *base_layout(),
                {"row": 2, "col": 2, "type": "knight", "color": "black"},
            ]
        ),
    )
    knight_game = use_scorch(client, knight_game, 3, 2).json()
    knight_moves = move_targets(knight_game, 2, 2)
    assert (4, 3) in knight_moves
    assert (3, 2) not in knight_moves


def test_scorch_blocks_elephant_movement_and_charges(client):
    payload = scorch_game(
        [
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 1, "col": 3, "type": "elephant", "color": "black"},
        ]
    )
    payload["configuration"]["enabledPieces"].append("elephant")
    payload["configuration"]["piecePoints"]["elephant"] = 7
    game = start_scorch_game(client, payload)
    game = use_scorch(client, game, 2, 3).json()

    elephant_moves = move_targets(game, 1, 3)
    assert (2, 3) not in elephant_moves
    assert (3, 3) not in elephant_moves


def test_scorch_can_legally_block_check_and_reset_removes_terrain(client):
    game = start_scorch_game(
        client,
        scorch_game(
            [
                {"row": 7, "col": 4, "type": "king", "color": "white"},
                {"row": 0, "col": 7, "type": "king", "color": "black"},
                {"row": 0, "col": 4, "type": "rook", "color": "black"},
            ]
        ),
    )
    assert game["gameStatus"] == "check"
    targets = scorch_targets(game)
    assert (3, 4) in targets
    assert (3, 3) not in targets

    blocked = use_scorch(client, game, 3, 4)
    assert blocked.status_code == 200, blocked.text
    result = blocked.json()
    assert result["gameStatus"] == "active"

    requested = client.post(
        f"/game/{game['id']}/rematch",
        json={
            "action": "request",
            "color": "white",
            "expectedVersion": result["version"],
        },
    ).json()
    reset = client.post(
        f"/game/{game['id']}/rematch",
        json={
            "action": "accept",
            "color": "black",
            "expectedVersion": requested["version"],
        },
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["terrain"] == []
