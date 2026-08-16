CLASSIC_TYPES = ["pawn", "knight", "bishop", "rook", "queen", "king"]


def elephant_game(
    placements: list[dict],
    *,
    piece_parameters: dict[str, int] | None = None,
    victory_mode: str = "checkmate",
) -> dict:
    return {
        "mode": "local",
        "boardRows": 8,
        "boardCols": 8,
        "configuration": {
            "schemaVersion": 2,
            "presetId": "elephant-test",
            "formationId": "custom",
            "enabledPieces": [*CLASSIC_TYPES, "elephant", "cannibal"],
            "piecePoints": {"king": 0, "elephant": 7, "cannibal": 6},
            "pieceParameters": (
                {"elephant": piece_parameters} if piece_parameters else {}
            ),
            "initialLayout": placements,
            "victory": {"mode": victory_mode},
            "specialAbilities": {"enabled": False, "allowed": []},
            "gambit": {"enabled": False},
        },
    }


def destinations(game: dict, row: int, col: int) -> set[tuple[int, int]]:
    return {
        (option["to"]["row"], option["to"]["col"])
        for option in game["validMoves"]
        if option["from"] == {"row": row, "col": col}
    }


def test_elephant_catalog_exposes_editable_defaults(client):
    catalog = client.get("/game/catalog").json()
    elephant = next(piece for piece in catalog["pieces"] if piece["type"] == "elephant")
    parameter_specs = {
        parameter["id"]: parameter for parameter in elephant["tunableParameters"]
    }
    parameters = {
        parameter["id"]: parameter["default"]
        for parameter in elephant["tunableParameters"]
    }

    assert elephant["points"] == 7
    assert parameters == {
        "movementDistance": 4,
        "chargeDistance": 2,
        "alliedChargeLimit": 1,
    }
    assert parameter_specs["alliedChargeLimit"]["maxParameter"] == "chargeDistance"
    assert any("Cannibal" in rule for rule in elephant["rules"])


def test_elephant_allied_charge_limit_cannot_exceed_charge_distance(client):
    payload = elephant_game(
        [
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 6, "col": 3, "type": "elephant", "color": "white"},
        ],
        piece_parameters={
            "movementDistance": 4,
            "chargeDistance": 2,
            "alliedChargeLimit": 3,
        },
    )

    validation = client.post("/game/validate", json=payload).json()
    assert validation["valid"] is False
    assert any(
        "Allied Charge Limit cannot exceed Charge Distance" in error
        for error in validation["errors"]
    )

    created = client.post("/game/create", json=payload)
    assert created.status_code == 400
    assert "Allied Charge Limit cannot exceed Charge Distance" in created.json()["detail"]


def test_elephant_moves_forward_or_sideways_but_captures_only_by_charge(client):
    payload = elephant_game(
        [
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 6, "col": 3, "type": "elephant", "color": "white"},
            {"row": 5, "col": 3, "type": "pawn", "color": "black"},
            {"row": 4, "col": 3, "type": "knight", "color": "black"},
        ]
    )
    created = client.post("/game/create", json=payload)
    assert created.status_code == 200, created.text
    game = created.json()["game"]
    moves = destinations(game, 6, 3)

    assert (5, 3) not in moves
    assert (4, 3) in moves
    assert (7, 3) not in moves
    assert {(6, 2), (6, 1), (6, 0), (6, 4), (6, 5), (6, 6), (6, 7)} <= moves

    charged = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 6,
            "fromCol": 3,
            "toRow": 4,
            "toCol": 3,
            "expectedVersion": game["version"],
        },
    )
    assert charged.status_code == 200, charged.text
    result = charged.json()
    assert result["board"][5][3] is None
    assert result["board"][4][3]["type"] == "elephant"
    assert [piece["type"] for piece in result["capturedPieces"]["white"]] == [
        "pawn",
        "knight",
    ]
    assert result["score"]["white"] == 4
    assert "removed 2 pieces" in result["lastMoveExplanation"]


def test_elephant_charge_allied_limit_and_own_king_are_enforced(client):
    blocked_by_allies = elephant_game(
        [
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 6, "col": 3, "type": "elephant", "color": "white"},
            {"row": 5, "col": 3, "type": "pawn", "color": "white"},
            {"row": 4, "col": 3, "type": "knight", "color": "white"},
        ]
    )
    game = client.post("/game/create", json=blocked_by_allies).json()["game"]
    assert (4, 3) not in destinations(game, 6, 3)

    editable_limit = elephant_game(
        blocked_by_allies["configuration"]["initialLayout"],
        piece_parameters={
            "movementDistance": 4,
            "chargeDistance": 2,
            "alliedChargeLimit": 2,
        },
    )
    game = client.post("/game/create", json=editable_limit).json()["game"]
    assert (4, 3) in destinations(game, 6, 3)

    own_king_in_lane = elephant_game(
        [
            {"row": 5, "col": 3, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 6, "col": 3, "type": "elephant", "color": "white"},
        ],
        piece_parameters={
            "movementDistance": 4,
            "chargeDistance": 2,
            "alliedChargeLimit": 2,
        },
    )
    game = client.post("/game/create", json=own_king_in_lane).json()["game"]
    assert (4, 3) not in destinations(game, 6, 3)


def test_elephant_collision_eliminates_both_elephants(client):
    payload = elephant_game(
        [
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 6, "col": 3, "type": "elephant", "color": "white"},
            {"row": 4, "col": 3, "type": "elephant", "color": "black"},
        ]
    )
    game = client.post("/game/create", json=payload).json()["game"]
    result = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 6,
            "fromCol": 3,
            "toRow": 4,
            "toCol": 3,
            "expectedVersion": game["version"],
        },
    ).json()

    assert result["board"][6][3] is None
    assert result["board"][4][3] is None
    assert [piece["type"] for piece in result["capturedPieces"]["white"]] == [
        "elephant"
    ]
    assert "both Elephants were eliminated" in result["lastMoveExplanation"]


def test_elephant_gives_charge_check_and_cannot_be_consumed(client):
    check_payload = elephant_game(
        [
            {"row": 3, "col": 3, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 1, "col": 3, "type": "elephant", "color": "black"},
        ]
    )
    game = client.post("/game/create", json=check_payload).json()["game"]
    assert game["gameStatus"] == "check"

    cannibal_payload = elephant_game(
        [
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 5, "col": 3, "type": "cannibal", "color": "white"},
            {"row": 6, "col": 3, "type": "elephant", "color": "black"},
        ]
    )
    game = client.post("/game/create", json=cannibal_payload).json()["game"]
    assert (6, 3) not in destinations(game, 5, 3)
