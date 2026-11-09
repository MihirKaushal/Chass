from __future__ import annotations


def dragon_definition() -> dict:
    return {
        "type": "dragon",
        "displayName": "Dragon",
        "symbols": {"white": "D", "black": "d"},
        "patterns": [
            {"dr": -2, "dc": -1, "relative_to_color": True},
            {"dr": -2, "dc": 1, "relative_to_color": True},
            {"dr": -1, "dc": -2, "relative_to_color": True},
            {"dr": -1, "dc": 2, "relative_to_color": True},
            {"dr": 1, "dc": -2, "relative_to_color": True},
            {"dr": 1, "dc": 2, "relative_to_color": True},
            {"dr": 2, "dc": -1, "relative_to_color": True},
            {"dr": 2, "dc": 1, "relative_to_color": True},
        ],
        "points": 4,
        "isCustom": True,
        "customAttributes": {
            "rules": ["Leaps in the same L-shaped pattern as a Knight."],
        },
        "metadata": {"family": "runtime-test"},
    }


def custom_game_payload(*, gambit: bool = False) -> dict:
    enabled = ["king", "dragon"] if gambit else [
        "pawn",
        "knight",
        "bishop",
        "rook",
        "queen",
        "king",
        "dragon",
    ]
    return {
        "mode": "local",
        "boardRows": 8,
        "boardCols": 8,
        "customPieces": [dragon_definition()],
        "configuration": {
            "schemaVersion": 2,
            "presetId": "runtime-custom",
            "formationId": "custom",
            "enabledPieces": enabled,
            "piecePoints": {"king": 0, "dragon": 4},
            "initialLayout": (
                []
                if gambit
                else [
                    {"row": 7, "col": 7, "type": "king", "color": "white"},
                    {"row": 0, "col": 7, "type": "king", "color": "black"},
                    {"row": 6, "col": 2, "type": "dragon", "color": "white"},
                    {"row": 1, "col": 2, "type": "dragon", "color": "black"},
                ]
            ),
            "victory": {"mode": "checkmate"},
            "specialAbilities": {"enabled": False, "allowed": []},
            "gambit": {
                "enabled": gambit,
                "budget": 12,
                "maxPieces": 4,
                "setupRows": 2,
                "maxQueens": 0,
                "pieceCaps": {"king": 1, "dragon": 3},
            },
        },
    }


def test_runtime_custom_piece_validates_creates_and_moves(client):
    payload = custom_game_payload()
    validation = client.post("/game/validate", json=payload)
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    created = client.post("/game/create", json=payload)
    assert created.status_code == 200, created.text
    game = created.json()["game"]
    assert "dragon" in game["configuration"]["enabledPieces"]
    dragon = next(
        definition
        for definition in game["pieceDefinitions"]
        if definition["type"] == "dragon"
    )
    assert dragon["displayName"] == "Dragon"
    assert dragon["points"] == 4
    assert dragon["isCustom"] is True
    assert any(
        option["from"] == {"row": 6, "col": 2}
        and option["to"] == {"row": 4, "col": 3}
        for option in game["validMoves"]
    )

    moved = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 6,
            "fromCol": 2,
            "toRow": 4,
            "toCol": 3,
            "expectedVersion": game["version"],
        },
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["board"][4][3]["type"] == "dragon"


def test_runtime_custom_piece_can_join_gambit_budget_and_deployment(client):
    response = client.post("/game/create", json=custom_game_payload(gambit=True))
    assert response.status_code == 200, response.text
    game = response.json()["game"]
    assert game["phase"] == "deployment"
    assert game["gambit"]["config"]["piecePoints"]["dragon"] == 4
    assert game["gambit"]["config"]["pieceCaps"]["dragon"] == 3

    king = client.post(
        f"/game/{game['id']}/gambit/deployment",
        json={
            "action": "place",
            "row": 7,
            "col": 4,
            "pieceType": "king",
            "expectedVersion": game["version"],
        },
    ).json()
    dragon = client.post(
        f"/game/{game['id']}/gambit/deployment",
        json={
            "action": "place",
            "row": 6,
            "col": 4,
            "pieceType": "dragon",
            "expectedVersion": king["version"],
        },
    )
    assert dragon.status_code == 200, dragon.text
    assert dragon.json()["gambit"]["setupSummary"]["pointsSpent"] == 4


def test_runtime_custom_piece_types_must_be_unique_identifiers(client):
    duplicate = custom_game_payload()
    duplicate["customPieces"].append(dragon_definition())
    response = client.post("/game/create", json=duplicate)
    assert response.status_code == 422
    assert "must be unique" in response.text

    invalid = custom_game_payload()
    invalid["customPieces"][0]["type"] = "Dragon Piece"
    response = client.post("/game/create", json=invalid)
    assert response.status_code == 422
