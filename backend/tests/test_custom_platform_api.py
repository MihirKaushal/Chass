from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.rules.variant_system import affinity_start_squares, barricade_start_squares


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def classic_types() -> list[str]:
    return ["pawn", "knight", "bishop", "rook", "queen", "king"]


def configured_game(**overrides) -> dict:
    configuration = {
        "schemaVersion": 2,
        "presetId": "test",
        "formationId": "custom",
        "enabledPieces": classic_types(),
        "piecePoints": {
            "pawn": 1,
            "knight": 3,
            "bishop": 3,
            "rook": 5,
            "queen": 9,
            "king": 0,
        },
        "initialLayout": [],
        "victory": {"mode": "checkmate"},
        "specialAbilities": {"enabled": False, "allowed": []},
        "gambit": {"enabled": False},
    }
    configuration.update(overrides)
    return {
        "mode": "local",
        "boardRows": 8,
        "boardCols": 8,
        "configuration": configuration,
    }


def start_local_ability_game(client, ability: str, **overrides) -> dict:
    payload = configured_game(
        specialAbilities={"enabled": True, "allowed": [ability]},
        **overrides,
    )
    game = client.post("/game/create", json=payload).json()["game"]
    white = client.post(
        f"/game/{game['id']}/ability",
        json={"abilityId": ability, "expectedVersion": game["version"]},
    ).json()
    handoff = client.post(
        f"/game/{game['id']}/setup/handoff",
        json={"expectedVersion": white["version"]},
    ).json()
    black = client.post(
        f"/game/{game['id']}/ability",
        json={"abilityId": ability, "expectedVersion": handoff["version"]},
    )
    assert black.status_code == 200
    return black.json()


def test_catalog_describes_custom_content(client):
    response = client.get("/game/catalog")
    assert response.status_code == 200
    catalog = response.json()

    assert catalog["schemaVersion"] == 2
    assert {piece["type"] for piece in catalog["pieces"]} >= {
        "maharani",
        "catapult",
        "barricade",
        "hypnotizer",
        "diplomat",
    }
    assert {ability["id"] for ability in catalog["specialAbilities"]} == {
        "necromancy",
        "getaway",
        "eye_for_an_eye",
        "kamikaze",
        "episcopal",
        "power_of_love",
    }
    assert all(piece["description"] and piece["movement"] for piece in catalog["pieces"])
    assert {formation["id"] for formation in catalog["formations"]} >= {
        "horde",
        "castle_siege",
    }
    cooldowns = {
        ability["id"]: ability.get("cooldownTurns") for ability in catalog["specialAbilities"]
    }
    assert cooldowns["necromancy"] == 9
    assert cooldowns["getaway"] is None
    assert cooldowns["eye_for_an_eye"] == 10
    assert cooldowns["episcopal"] == 6
    getaway = next(ability for ability in catalog["specialAbilities"] if ability["id"] == "getaway")
    assert "Queen" in getaway["summary"]
    assert "Rook" not in getaway["summary"]
    assert any("Only a Queen" in detail for detail in getaway["details"])
    assert getaway["usageLimit"] == 1
    assert "center_dominion" in {mode["id"] for mode in catalog["victoryModes"]}
    assert "center_dominion" in {mode["id"] for mode in catalog["popularModes"]}
    draft_mode = next(mode for mode in catalog["popularModes"] if mode["id"] == "draft_gambit")
    assert draft_mode["gambit"] == {"enabled": True, "draftEnabled": True}
    assert catalog["gambit"]["draftDetails"]


def test_catalog_formations_have_complete_horde_and_castle_armies(client):
    catalog = client.get("/game/catalog").json()
    formations = {formation["id"]: formation for formation in catalog["formations"]}

    horde = formations["horde"]["initialLayout"]
    assert {"row": 7, "col": 4, "type": "king", "color": "white"} in horde
    assert {"row": 5, "col": 0, "type": "pawn", "color": "white"} in horde

    castle = formations["castle_siege"]["initialLayout"]
    for color in ("white", "black"):
        pieces = [piece for piece in castle if piece["color"] == color]
        assert sum(piece["type"] == "rook" for piece in pieces) == 4
        assert sum(piece["type"] == "pawn" for piece in pieces) == 10
        assert sum(piece["type"] == "knight" for piece in pieces) == 2


def test_configuration_validation_disables_incompatible_horde_rules(client):
    catalog = client.get("/game/catalog").json()
    horde = next(item for item in catalog["formations"] if item["id"] == "horde")
    payload = configured_game(
        formationId="horde",
        initialLayout=horde["initialLayout"],
        victory={"mode": "checkmate"},
    )

    invalid = client.post("/game/validate", json=payload)
    assert invalid.status_code == 200
    result = invalid.json()
    assert result["valid"] is False
    assert "checkmate" in result["disabledOptions"]["victoryModes"]
    assert any("elimination" in error.lower() for error in result["errors"])

    payload["configuration"]["victory"] = {"mode": "elimination"}
    valid = client.post("/game/validate", json=payload).json()
    assert valid["valid"] is True


def test_configuration_warns_when_getaway_players_have_no_queens(client):
    payload = configured_game(
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 7, "col": 0, "type": "rook", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 0, "col": 0, "type": "rook", "color": "black"},
        ],
        specialAbilities={"enabled": True, "allowed": ["getaway"]},
    )

    result = client.post("/game/validate", json=payload).json()

    assert result["valid"] is True
    assert "Getaway requires a Queen for both players." in result["warnings"]


def test_horde_castle_and_sixteen_square_presets_create_playable_boards(client):
    catalog = client.get("/game/catalog").json()
    formations = {item["id"]: item for item in catalog["formations"]}

    for formation_id, victory in (("horde", "elimination"), ("castle_siege", "checkmate")):
        formation = formations[formation_id]
        payload = configured_game(
            formationId=formation_id,
            initialLayout=formation["initialLayout"],
            victory={"mode": victory},
        )
        payload["boardRows"] = formation["boardRows"]
        payload["boardCols"] = formation["boardCols"]
        created = client.post("/game/create", json=payload)
        assert created.status_code == 200
        assert created.json()["game"]["gameStatus"] in {"active", "check"}

    large = configured_game()
    large["boardRows"] = 16
    large["boardCols"] = 16
    created = client.post("/game/create", json=large)
    assert created.status_code == 200
    game = created.json()["game"]
    assert game["boardRows"] == 16
    assert game["boardCols"] == 16
    assert len(game["board"]) == 16
    assert all(len(row) == 16 for row in game["board"])


def test_multiple_barricades_spawn_in_the_board_center(client):
    payload = configured_game(
        barricadeCount=4,
        enabledPieces=[*classic_types(), "barricade"],
        piecePoints={
            "pawn": 1,
            "knight": 3,
            "bishop": 3,
            "rook": 5,
            "queen": 9,
            "king": 0,
            "barricade": 0,
        },
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 6, "col": 0, "type": "rook", "color": "white"},
            {"row": 1, "col": 0, "type": "rook", "color": "black"},
        ],
    )
    created = client.post("/game/create", json=payload)
    assert created.status_code == 200
    board = created.json()["game"]["board"]
    barricades = [
        (row, col)
        for row, board_row in enumerate(board)
        for col, piece in enumerate(board_row)
        if piece and piece["type"] == "barricade"
    ]
    assert barricades == [(3, 3), (3, 4), (4, 3), (4, 4)]


def test_center_geometry_adapts_to_even_and_odd_board_heights(client):
    assert set(barricade_start_squares(8, 8, 4)) == {
        (3, 3),
        (3, 4),
        (4, 3),
        (4, 4),
    }
    assert set(barricade_start_squares(7, 7, 4)) == {
        (3, 1),
        (3, 2),
        (3, 4),
        (3, 5),
    }
    assert affinity_start_squares(8, 8) == {
        "white": [(3, 3), (4, 4)],
        "black": [(3, 4), (4, 3)],
    }
    assert affinity_start_squares(7, 7) == {
        "white": [(3, 1), (3, 4)],
        "black": [(3, 2), (3, 5)],
    }

    payload = configured_game(
        gambit={
            "enabled": True,
            "budget": 39,
            "maxPieces": 14,
            "setupRows": 2,
            "maxQueens": 2,
            "affinityEnabled": True,
            "commandPointCap": 3,
        }
    )
    payload["boardRows"] = 7
    payload["boardCols"] = 7
    created = client.post("/game/create", json=payload)
    assert created.status_code == 200
    affinity = created.json()["game"]["gambit"]["config"]["affinitySquares"]
    assert affinity == {
        "white": [{"row": 3, "col": 1}, {"row": 3, "col": 4}],
        "black": [{"row": 3, "col": 2}, {"row": 3, "col": 5}],
    }


def test_custom_piece_points_reject_negative_values(client):
    payload = configured_game(piecePoints={"pawn": -1})
    response = client.post("/game/create", json=payload)
    assert response.status_code == 422

    payload = configured_game(piecePoints={"pawn": 100001})
    response = client.post("/game/create", json=payload)
    assert response.status_code == 422


def test_configured_gambit_allows_locking_in_below_maximum_budget(client):
    payload = configured_game(
        gambit={
            "enabled": True,
            "budget": 5,
            "maxPieces": 4,
            "setupRows": 2,
            "maxQueens": 1,
            "affinityEnabled": True,
            "commandPointCap": 3,
        }
    )
    created = client.post("/game/create", json=payload)
    assert created.status_code == 200
    game = created.json()["game"]

    king = client.post(
        f"/game/{game['id']}/gambit/deployment",
        json={
            "action": "place",
            "row": 7,
            "col": 4,
            "pieceType": "king",
            "expectedVersion": game["version"],
        },
    )
    assert king.status_code == 200
    setup = king.json()
    assert setup["gambit"]["setupSummary"]["pointsSpent"] == 0
    assert setup["gambit"]["setupSummary"]["pointsRemaining"] == 5
    ready = client.post(
        f"/game/{game['id']}/gambit/ready",
        json={"expectedVersion": setup["version"]},
    )
    assert ready.status_code == 200
    locked = ready.json()
    assert locked["phase"] == "handoff"
    assert locked["gambit"]["config"]["requireExactBudget"] is False


def test_catapult_action_creates_public_countdown_and_tooltip_runtime(client):
    layout = [
        {"row": 7, "col": 4, "type": "king", "color": "white"},
        {"row": 0, "col": 4, "type": "king", "color": "black"},
        {"row": 6, "col": 4, "type": "catapult", "color": "white"},
        {"row": 4, "col": 4, "type": "rook", "color": "black"},
    ]
    payload = configured_game(
        enabledPieces=[*classic_types(), "catapult"],
        piecePoints={
            "pawn": 1,
            "knight": 3,
            "bishop": 3,
            "rook": 5,
            "queen": 9,
            "king": 0,
            "catapult": 5,
        },
        initialLayout=layout,
        victory={"mode": "king_capture", "kingPoints": 1},
    )
    created = client.post("/game/create", json=payload)
    assert created.status_code == 200
    game = created.json()["game"]
    projectile = next(
        action
        for action in game["availableActions"]
        if action["actionType"] == "catapult_projectile"
    )

    fired = client.post(
        f"/game/{game['id']}/action",
        json={
            "actionType": projectile["actionType"],
            "source": projectile["source"],
            "target": projectile["target"],
            "expectedVersion": game["version"],
        },
    )
    assert fired.status_code == 200
    updated = fired.json()
    countdown = next(item for item in updated["countdowns"] if item["kind"] == "catapult")
    catapult = updated["board"][6][4]

    assert countdown["owner"] == "white"
    assert countdown["remainingTurns"] == 2
    assert catapult["runtime"]["catapult_ready_turn_remaining"] == 2
    assert updated["board"][4][4] is None


def test_online_ability_choices_stay_private_until_both_lock(client):
    payload = configured_game(
        specialAbilities={
            "enabled": True,
            "allowed": ["getaway", "power_of_love"],
        }
    )
    payload["mode"] = "online"
    created = client.post("/game/create", json=payload).json()
    joined = client.post(
        "/game/join",
        json={"inviteToken": created["inviteToken"]},
    ).json()

    white_choice = client.post(
        f"/game/{created['game']['id']}/ability",
        headers=auth(created["playerToken"]),
        json={
            "abilityId": "getaway",
            "expectedVersion": joined["game"]["version"],
        },
    )
    assert white_choice.status_code == 200

    black_view = client.get(
        f"/game/{created['game']['id']}",
        headers=auth(joined["playerToken"]),
    ).json()
    assert black_view["abilities"]["selected"]["white"] == "locked"

    black_choice = client.post(
        f"/game/{created['game']['id']}/ability",
        headers=auth(joined["playerToken"]),
        json={
            "abilityId": "power_of_love",
            "expectedVersion": black_view["version"],
        },
    )
    assert black_choice.status_code == 200
    game = black_choice.json()
    assert game["phase"] == "play"
    assert game["abilities"]["selected"] == {
        "white": "getaway",
        "black": "power_of_love",
    }


def test_point_race_resolves_before_no_move_fallback(client):
    payload = configured_game(
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 4, "col": 0, "type": "rook", "color": "white"},
            {"row": 4, "col": 2, "type": "pawn", "color": "black"},
        ],
        victory={"mode": "point_race", "targetPoints": 1, "kingPoints": 0},
    )
    game = client.post("/game/create", json=payload).json()["game"]
    configured_rule = next(rule for rule in game["rules"] if rule["id"] == "configured_victory")
    assert configured_rule["name"] == "Point Race"
    assert configured_rule["isSpecial"] is True

    response = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 4,
            "fromCol": 0,
            "toRow": 4,
            "toCol": 2,
            "expectedVersion": game["version"],
        },
    )
    assert response.status_code == 200
    finished = response.json()
    assert finished["gameStatus"] == "points"
    assert finished["winner"] == "white"
    assert finished["result"]["reasonCode"] == "point_target"


def test_center_dominion_wins_after_surviving_the_opponent_turn(client):
    payload = configured_game(
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 0, "type": "king", "color": "black"},
            {"row": 3, "col": 3, "type": "knight", "color": "white"},
            {"row": 4, "col": 4, "type": "knight", "color": "white"},
            {"row": 3, "col": 4, "type": "knight", "color": "black"},
            {"row": 4, "col": 3, "type": "knight", "color": "black"},
        ],
        victory={"mode": "center_dominion", "dominionRounds": 1},
    )
    game = client.post("/game/create", json=payload).json()["game"]

    assert game["centerDominion"] == {
        "targetRounds": 1,
        "progress": {"white": 0, "black": 0},
        "primed": {"white": False, "black": False},
        "controlled": {"white": True, "black": True},
        "squares": {
            "white": [{"row": 3, "col": 3}, {"row": 4, "col": 4}],
            "black": [{"row": 3, "col": 4}, {"row": 4, "col": 3}],
        },
    }

    white_move = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 7,
            "fromCol": 7,
            "toRow": 7,
            "toCol": 6,
            "expectedVersion": game["version"],
        },
    )
    assert white_move.status_code == 200
    after_white = white_move.json()
    assert after_white["centerDominion"]["primed"]["white"] is True

    black_move = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 0,
            "fromCol": 0,
            "toRow": 0,
            "toCol": 1,
            "expectedVersion": after_white["version"],
        },
    )
    assert black_move.status_code == 200
    finished = black_move.json()
    assert finished["gameStatus"] == "center_dominion"
    assert finished["winner"] == "white"
    assert finished["result"]["reasonCode"] == "center_dominion"
    assert "held both center squares" in finished["result"]["description"]


def test_barricade_must_be_single_neutral_and_centered(client):
    payload = configured_game(
        enabledPieces=[*classic_types(), "barricade"],
        piecePoints={
            "pawn": 1,
            "knight": 3,
            "bishop": 3,
            "rook": 5,
            "queen": 9,
            "king": 0,
            "barricade": 0,
        },
        initialLayout=[
            {"row": 7, "col": 4, "type": "king", "color": "white"},
            {"row": 0, "col": 4, "type": "king", "color": "black"},
            {"row": 2, "col": 2, "type": "barricade", "color": "neutral"},
        ],
    )
    response = client.post("/game/create", json=payload)
    assert response.status_code == 400
    assert "central" in response.json()["detail"]

    payload["configuration"]["initialLayout"][-1] = {
        "row": 3,
        "col": 3,
        "type": "barricade",
        "color": "white",
    }
    response = client.post("/game/create", json=payload)
    assert response.status_code == 400
    assert "neutral" in response.json()["detail"]


def test_clock_expiry_is_resolved_and_persisted_on_refresh(client):
    from backend.routes.game import game_service

    payload = configured_game(victory={"mode": "timed", "timeSeconds": 30})
    created = client.post("/game/create", json=payload).json()["game"]
    record = game_service.repository.get_game(created["id"])
    assert record is not None and record.state.clock is not None

    state = record.state.clone()
    state.clock.remaining_seconds["white"] = 0
    state.clock.turn_started_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    prepared = game_service.repository.save_game(
        state,
        record.version,
        expires_at=record.expires_at,
    )

    response = client.get(f"/game/{created['id']}")
    assert response.status_code == 200
    finished = response.json()
    assert finished["version"] == prepared.version + 1
    assert finished["gameStatus"] == "time"
    assert finished["winner"] == "black"
    assert finished["result"]["reasonCode"] == "time_expired"

    persisted = game_service.repository.get_game(created["id"])
    assert persisted is not None
    assert persisted.state.phase == "finished"
    assert persisted.state.result is not None
    assert persisted.state.result.reason_code == "time_expired"


def test_standard_promotion_stays_available_when_piece_is_not_in_starting_catalog(client):
    payload = configured_game(
        enabledPieces=["pawn", "king"],
        piecePoints={"pawn": 1, "king": 0},
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 1, "col": 0, "type": "pawn", "color": "white"},
        ],
    )
    game = client.post("/game/create", json=payload).json()["game"]
    assert "queen" not in game["configuration"]["enabledPieces"]
    assert "queen" in {definition["type"] for definition in game["pieceDefinitions"]}

    forged = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 1,
            "fromCol": 0,
            "toRow": 0,
            "toCol": 0,
            "promotion": "kamikaze",
            "expectedVersion": game["version"],
        },
    )
    assert forged.status_code == 400
    assert "selected ability" in forged.json()["detail"]

    promoted = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 1,
            "fromCol": 0,
            "toRow": 0,
            "toCol": 0,
            "promotion": "queen",
            "expectedVersion": game["version"],
        },
    )
    assert promoted.status_code == 200
    assert promoted.json()["board"][0][0]["type"] == "queen"


def test_catapult_does_not_attack_while_recovering(client):
    payload = configured_game(
        enabledPieces=[*classic_types(), "catapult"],
        piecePoints={
            "pawn": 1,
            "knight": 3,
            "bishop": 3,
            "rook": 5,
            "queen": 9,
            "king": 0,
            "catapult": 5,
        },
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 5, "col": 4, "type": "king", "color": "black"},
            {"row": 6, "col": 4, "type": "catapult", "color": "white"},
            {"row": 4, "col": 4, "type": "rook", "color": "black"},
        ],
    )
    game = client.post("/game/create", json=payload).json()["game"]
    action = next(
        item
        for item in game["availableActions"]
        if item["actionType"] == "catapult_projectile" and item["target"] == {"row": 4, "col": 4}
    )
    fired = client.post(
        f"/game/{game['id']}/action",
        json={
            "actionType": action["actionType"],
            "source": action["source"],
            "target": action["target"],
            "expectedVersion": game["version"],
        },
    )
    assert fired.status_code == 200
    assert fired.json()["currentPlayer"] == "black"
    assert fired.json()["gameStatus"] == "active"


def test_diplomat_contact_is_public_and_attached_to_piece_runtime(client):
    payload = configured_game(
        enabledPieces=[*classic_types(), "diplomat"],
        piecePoints={
            "pawn": 1,
            "knight": 3,
            "bishop": 3,
            "rook": 5,
            "queen": 9,
            "king": 0,
            "diplomat": 4,
        },
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 6, "col": 0, "type": "diplomat", "color": "white"},
            {"row": 5, "col": 0, "type": "pawn", "color": "black"},
            {"row": 7, "col": 0, "type": "rook", "color": "white"},
        ],
    )
    game = client.post("/game/create", json=payload).json()["game"]
    moved = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 7,
            "fromCol": 0,
            "toRow": 7,
            "toCol": 1,
            "expectedVersion": game["version"],
        },
    )
    assert moved.status_code == 200
    updated = moved.json()
    countdown = next(item for item in updated["countdowns"] if item["kind"] == "diplomat_contact")
    diplomat = updated["board"][6][0]
    assert countdown["owner"] == "white"
    assert countdown["remainingTurns"] == 1
    assert diplomat["runtime"]["diplomat_contacts_status"] == [
        {"targetName": "Pawn", "progress": 1, "required": 2}
    ]


def test_gambit_point_limit_does_not_require_an_exact_piece_total(client):
    payload = configured_game(
        enabledPieces=["pawn", "king"],
        piecePoints={"pawn": 3, "king": 0},
        gambit={
            "enabled": True,
            "budget": 2,
            "maxPieces": 2,
            "setupRows": 1,
            "maxQueens": 0,
            "affinityEnabled": False,
            "commandPointCap": 3,
            "pieceCaps": {"pawn": 1, "king": 1},
        },
    )
    response = client.post("/game/create", json=payload)
    assert response.status_code == 200
    game = response.json()["game"]
    assert game["gambit"]["config"]["budget"] == 2
    assert game["gambit"]["config"]["requireExactBudget"] is False


def test_gambit_point_limit_must_cover_the_required_king(client):
    payload = configured_game(
        enabledPieces=["king"],
        piecePoints={"king": 3},
        gambit={
            "enabled": True,
            "budget": 2,
            "maxPieces": 1,
            "setupRows": 1,
            "maxQueens": 0,
            "affinityEnabled": False,
            "commandPointCap": 3,
            "pieceCaps": {"king": 1},
        },
    )
    response = client.post("/game/create", json=payload)
    assert response.status_code == 400
    assert "required King" in response.json()["detail"]


def test_online_timed_clock_starts_only_after_second_player_joins(client):
    payload = configured_game(victory={"mode": "timed", "timeSeconds": 30})
    payload["mode"] = "online"
    created = client.post("/game/create", json=payload).json()
    assert created["game"]["phase"] == "lobby"

    joined = client.post(
        "/game/join",
        json={"inviteToken": created["inviteToken"]},
    )
    assert joined.status_code == 200
    game = joined.json()["game"]
    assert game["phase"] == "play"
    assert game["clock"]["activeColor"] == "white"
    assert game["clock"]["remainingSeconds"]["white"] > 29


def test_timed_gambit_clock_restarts_when_hidden_armies_reveal(client):
    from backend.routes.game import game_service

    payload = configured_game(
        enabledPieces=["king"],
        piecePoints={"king": 0},
        victory={"mode": "timed", "timeSeconds": 30},
        gambit={
            "enabled": True,
            "budget": 0,
            "maxPieces": 1,
            "setupRows": 2,
            "maxQueens": 0,
            "affinityEnabled": False,
            "commandPointCap": 3,
            "pieceCaps": {"king": 1},
        },
    )
    game = client.post("/game/create", json=payload).json()["game"]
    record = game_service.repository.get_game(game["id"])
    assert record is not None and record.state.clock is not None
    old_state = record.state.clone()
    old_state.clock.turn_started_at = datetime.now(timezone.utc) - timedelta(hours=1)
    prepared = game_service.repository.save_game(
        old_state,
        record.version,
        expires_at=record.expires_at,
    )

    white_king = client.post(
        f"/game/{game['id']}/gambit/deployment",
        json={
            "action": "place",
            "row": 7,
            "col": 4,
            "pieceType": "king",
            "expectedVersion": prepared.version,
        },
    ).json()
    white_ready = client.post(
        f"/game/{game['id']}/gambit/ready",
        json={"expectedVersion": white_king["version"]},
    ).json()
    handoff = client.post(
        f"/game/{game['id']}/gambit/handoff",
        json={"expectedVersion": white_ready["version"]},
    ).json()
    black_king = client.post(
        f"/game/{game['id']}/gambit/deployment",
        json={
            "action": "place",
            "row": 0,
            "col": 4,
            "pieceType": "king",
            "expectedVersion": handoff["version"],
        },
    ).json()
    revealed = client.post(
        f"/game/{game['id']}/gambit/ready",
        json={"expectedVersion": black_king["version"]},
    )
    assert revealed.status_code == 200
    finished_setup = revealed.json()
    assert finished_setup["phase"] == "play"
    assert finished_setup["clock"]["remainingSeconds"]["white"] > 29


def test_eye_for_an_eye_removes_matching_pieces_without_scoring(client):
    game = start_local_ability_game(
        client,
        "eye_for_an_eye",
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 7, "col": 0, "type": "rook", "color": "white"},
            {"row": 0, "col": 0, "type": "rook", "color": "black"},
        ],
    )
    action = next(
        item for item in game["availableActions"] if item["actionType"] == "eye_for_an_eye"
    )
    response = client.post(
        f"/game/{game['id']}/action",
        json={
            "actionType": action["actionType"],
            "source": action["source"],
            "target": action["target"],
            "expectedVersion": game["version"],
        },
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["board"][7][0] is None
    assert updated["board"][0][0] is None
    assert updated["score"] == {"white": 0, "black": 0}
    assert updated["abilities"]["used"]["white"] is True
    assert updated["abilities"]["cooldowns"]["white"]["eye_for_an_eye"] == 10
    assert updated["abilities"]["usageCount"]["white"]["eye_for_an_eye"] == 1
    assert any(
        item["kind"] == "eye_for_an_eye" and item["remainingTurns"] == 10
        for item in updated["countdowns"]
    )


def test_episcopal_shift_exposes_six_turn_countdown_on_bishop(client):
    game = start_local_ability_game(
        client,
        "episcopal",
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 6, "col": 2, "type": "bishop", "color": "white"},
        ],
    )
    action = next(
        item
        for item in game["availableActions"]
        if item["actionType"] == "episcopal" and item["target"] == {"row": 5, "col": 2}
    )
    shifted = client.post(
        f"/game/{game['id']}/action",
        json={
            "actionType": action["actionType"],
            "source": action["source"],
            "target": action["target"],
            "expectedVersion": game["version"],
        },
    )
    assert shifted.status_code == 200
    updated = shifted.json()
    countdown = next(item for item in updated["countdowns"] if item["kind"] == "episcopal")
    assert countdown["remainingTurns"] == 6
    assert updated["board"][5][2]["runtime"]["episcopal_ready_turn_remaining"] == 6


def test_power_of_love_grants_queen_mobility_after_queen_capture(client):
    game = start_local_ability_game(
        client,
        "power_of_love",
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 6, "col": 0, "type": "queen", "color": "white"},
            {"row": 5, "col": 0, "type": "rook", "color": "black"},
        ],
    )
    white_move = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 7,
            "fromCol": 7,
            "toRow": 7,
            "toCol": 6,
            "expectedVersion": game["version"],
        },
    ).json()
    captured = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 5,
            "fromCol": 0,
            "toRow": 6,
            "toCol": 0,
            "expectedVersion": white_move["version"],
        },
    )
    assert captured.status_code == 200
    updated = captured.json()
    king = updated["board"][7][6]
    assert king["runtime"]["love_until_turn_remaining"] == 10
    assert any(
        move["from"] == {"row": 7, "col": 6} and move["to"] == {"row": 4, "col": 3}
        for move in updated["validMoves"]
    )


def test_necromancy_spends_score_and_recruits_captured_enemy(client):
    game = start_local_ability_game(
        client,
        "necromancy",
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 4, "col": 0, "type": "rook", "color": "white"},
            {"row": 4, "col": 2, "type": "pawn", "color": "black"},
        ],
    )
    capture = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 4,
            "fromCol": 0,
            "toRow": 4,
            "toCol": 2,
            "expectedVersion": game["version"],
        },
    ).json()
    black_move = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 0,
            "fromCol": 7,
            "toRow": 1,
            "toCol": 7,
            "expectedVersion": capture["version"],
        },
    ).json()
    action = next(
        item for item in black_move["availableActions"] if item["actionType"] == "necromancy"
    )
    recruited = client.post(
        f"/game/{game['id']}/action",
        json={
            "actionType": action["actionType"],
            "target": action["target"],
            "params": action["params"],
            "expectedVersion": black_move["version"],
        },
    )
    assert recruited.status_code == 200
    updated = recruited.json()
    revived = updated["board"][action["target"]["row"]][action["target"]["col"]]
    assert revived["type"] == "pawn"
    assert revived["color"] == "white"
    assert updated["spentScore"]["white"] == 1
    assert updated["score"]["white"] == 0
    assert updated["abilities"]["cooldowns"]["white"]["necromancy"] == 9
    assert any(
        item["kind"] == "necromancy" and item["remainingTurns"] == 9
        for item in updated["countdowns"]
    )


def test_kamikaze_final_rank_blast_ends_game_when_king_is_in_range(client):
    game = start_local_ability_game(
        client,
        "kamikaze",
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 2, "type": "king", "color": "black"},
            {"row": 1, "col": 0, "type": "pawn", "color": "white"},
        ],
    )
    detonated = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 1,
            "fromCol": 0,
            "toRow": 0,
            "toCol": 0,
            "promotion": "kamikaze",
            "expectedVersion": game["version"],
        },
    )
    assert detonated.status_code == 200
    updated = detonated.json()
    assert updated["gameStatus"] == "checkmate"
    assert updated["winner"] == "white"
    assert updated["result"]["reasonCode"] == "kamikaze"


def test_getaway_swaps_the_king_with_a_queen_to_escape_checkmate(client):
    game = start_local_ability_game(
        client,
        "getaway",
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "queen", "color": "white"},
            {"row": 1, "col": 6, "type": "pawn", "color": "white"},
            {"row": 1, "col": 0, "type": "king", "color": "black"},
            {"row": 7, "col": 0, "type": "rook", "color": "black"},
            {"row": 5, "col": 6, "type": "queen", "color": "black"},
        ],
    )
    assert game["gameStatus"] == "check"
    assert game["validMoves"] == []
    getaway = next(item for item in game["availableActions"] if item["actionType"] == "getaway")
    escaped = client.post(
        f"/game/{game['id']}/action",
        json={
            "actionType": getaway["actionType"],
            "source": getaway["source"],
            "target": getaway["target"],
            "expectedVersion": game["version"],
        },
    )
    assert escaped.status_code == 200
    updated = escaped.json()
    assert updated["board"][0][7]["type"] == "king"
    assert updated["board"][7][7]["type"] == "queen"
    assert updated["abilities"]["used"]["white"] is True
    assert updated["abilities"]["cooldowns"]["white"].get("getaway") is None
    assert not any(item["kind"] == "getaway" for item in updated["countdowns"])
    assert updated["abilities"]["usageCount"]["white"]["getaway"] == 1
    assert updated["currentPlayer"] == "black"


def test_getaway_does_not_offer_a_rook_swap(client):
    game = start_local_ability_game(
        client,
        "getaway",
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "rook", "color": "white"},
            {"row": 1, "col": 6, "type": "pawn", "color": "white"},
            {"row": 1, "col": 0, "type": "king", "color": "black"},
            {"row": 7, "col": 0, "type": "rook", "color": "black"},
            {"row": 5, "col": 6, "type": "queen", "color": "black"},
        ],
    )

    assert game["gameStatus"] == "checkmate"
    assert game["winner"] == "black"
    assert not any(item["actionType"] == "getaway" for item in game["availableActions"])


def test_maharani_can_cross_exactly_one_blocker_to_capture(client):
    payload = configured_game(
        enabledPieces=[*classic_types(), "maharani"],
        piecePoints={
            "pawn": 1,
            "knight": 3,
            "bishop": 3,
            "rook": 5,
            "queen": 9,
            "king": 0,
            "maharani": 13,
        },
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 7, "col": 0, "type": "maharani", "color": "white"},
            {"row": 6, "col": 0, "type": "pawn", "color": "white"},
            {"row": 4, "col": 0, "type": "rook", "color": "black"},
        ],
    )
    game = client.post("/game/create", json=payload).json()["game"]
    assert any(
        move["from"] == {"row": 7, "col": 0} and move["to"] == {"row": 4, "col": 0}
        for move in game["validMoves"]
    )
    captured = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 7,
            "fromCol": 0,
            "toRow": 4,
            "toCol": 0,
            "expectedVersion": game["version"],
        },
    )
    assert captured.status_code == 200
    assert captured.json()["board"][4][0]["type"] == "maharani"


def test_barricade_is_neutral_and_movable_only_through_special_action(client):
    payload = configured_game(
        enabledPieces=[*classic_types(), "barricade"],
        piecePoints={
            "pawn": 1,
            "knight": 3,
            "bishop": 3,
            "rook": 5,
            "queen": 9,
            "king": 0,
            "barricade": 0,
        },
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 3, "col": 3, "type": "barricade", "color": "neutral"},
            {"row": 4, "col": 3, "type": "pawn", "color": "white"},
        ],
    )
    game = client.post("/game/create", json=payload).json()["game"]
    action = next(
        item
        for item in game["availableActions"]
        if item["actionType"] == "move_barricade" and item["target"] == {"row": 3, "col": 2}
    )
    moved = client.post(
        f"/game/{game['id']}/action",
        json={
            "actionType": action["actionType"],
            "source": action["source"],
            "target": action["target"],
            "expectedVersion": game["version"],
        },
    )
    assert moved.status_code == 200
    updated = moved.json()
    assert updated["board"][3][3] is None
    assert updated["board"][3][2]["color"] == "neutral"


def test_either_rook_can_sacrifice_itself_to_demolish_a_visible_barricade(client):
    payload = configured_game(
        enabledPieces=[*classic_types(), "barricade"],
        piecePoints={
            "pawn": 1,
            "knight": 3,
            "bishop": 3,
            "rook": 5,
            "queen": 9,
            "king": 0,
            "barricade": 0,
        },
        initialLayout=[
            {"row": 7, "col": 6, "type": "king", "color": "white"},
            {"row": 0, "col": 6, "type": "king", "color": "black"},
            {"row": 3, "col": 0, "type": "rook", "color": "white"},
            {"row": 3, "col": 7, "type": "rook", "color": "black"},
            {"row": 3, "col": 3, "type": "barricade", "color": "neutral"},
        ],
    )
    game = client.post("/game/create", json=payload).json()["game"]
    white_action = next(
        action
        for action in game["availableActions"]
        if action["actionType"] == "demolish_barricade"
    )
    assert white_action["source"] == {"row": 3, "col": 0}
    assert white_action["target"] == {"row": 3, "col": 3}

    demolished = client.post(
        f"/game/{game['id']}/action",
        json={
            "actionType": white_action["actionType"],
            "source": white_action["source"],
            "target": white_action["target"],
            "expectedVersion": game["version"],
        },
    )
    assert demolished.status_code == 200
    result = demolished.json()
    assert result["board"][3][0] is None
    assert result["board"][3][3] is None
    assert result["score"] == {"white": 0, "black": 0}
    assert result["capturedPieces"] == {"white": [], "black": []}
    assert result["history"][-1]["actionType"] == "demolish_barricade"
    assert len(result["history"][-1]["captures"]) == 2

    second_game = client.post("/game/create", json=payload).json()["game"]
    after_white = client.post(
        f"/game/{second_game['id']}/move",
        json={
            "fromRow": 7,
            "fromCol": 6,
            "toRow": 7,
            "toCol": 5,
            "expectedVersion": second_game["version"],
        },
    ).json()
    assert any(
        action["actionType"] == "demolish_barricade" and action["source"] == {"row": 3, "col": 7}
        for action in after_white["availableActions"]
    )


def test_hypnotizer_recruits_weak_piece_after_three_owner_turns(client):
    payload = configured_game(
        enabledPieces=[*classic_types(), "hypnotizer"],
        piecePoints={
            "pawn": 1,
            "knight": 3,
            "bishop": 3,
            "rook": 5,
            "queen": 9,
            "king": 0,
            "hypnotizer": 6,
        },
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 6, "col": 0, "type": "hypnotizer", "color": "white"},
            {"row": 5, "col": 0, "type": "pawn", "color": "black"},
        ],
    )
    game = client.post("/game/create", json=payload).json()["game"]
    sequence = [
        (7, 7, 7, 6),
        (0, 7, 0, 6),
        (7, 6, 7, 7),
        (0, 6, 0, 7),
        (7, 7, 7, 6),
    ]
    for from_row, from_col, to_row, to_col in sequence:
        response = client.post(
            f"/game/{game['id']}/move",
            json={
                "fromRow": from_row,
                "fromCol": from_col,
                "toRow": to_row,
                "toCol": to_col,
                "expectedVersion": game["version"],
            },
        )
        assert response.status_code == 200
        game = response.json()
    assert game["board"][5][0]["type"] == "pawn"
    assert game["board"][5][0]["color"] == "white"


def test_diplomat_pacifies_for_five_target_turns_after_second_contact(client):
    payload = configured_game(
        enabledPieces=[*classic_types(), "diplomat"],
        piecePoints={
            "pawn": 1,
            "knight": 3,
            "bishop": 3,
            "rook": 5,
            "queen": 9,
            "king": 0,
            "diplomat": 4,
        },
        initialLayout=[
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 6, "col": 0, "type": "diplomat", "color": "white"},
            {"row": 5, "col": 0, "type": "pawn", "color": "black"},
        ],
    )
    game = client.post("/game/create", json=payload).json()["game"]
    for from_row, from_col, to_row, to_col in [
        (7, 7, 7, 6),
        (0, 7, 0, 6),
        (7, 6, 7, 7),
    ]:
        response = client.post(
            f"/game/{game['id']}/move",
            json={
                "fromRow": from_row,
                "fromCol": from_col,
                "toRow": to_row,
                "toCol": to_col,
                "expectedVersion": game["version"],
            },
        )
        assert response.status_code == 200
        game = response.json()
    pawn = game["board"][5][0]
    countdown = next(item for item in game["countdowns"] if item["kind"] == "pacified")
    assert pawn["runtime"]["pacified_until_turn_remaining"] == 5
    assert countdown["remainingTurns"] == 5
    assert not any(move["from"] == {"row": 5, "col": 0} for move in game["validMoves"])
