from backend.analysis.classic import classic_position_fen
from backend.models.domain import GameState
from backend.routes.game import game_service


def payload(pieces=None, **details):
    board = [[None] * 8 for _ in range(8)]
    for square, label in (
        pieces or {"e1": "white-king", "e8": "black-king", "a2": "white-pawn", "h7": "black-pawn"}
    ).items():
        board[8 - int(square[1])][ord(square[0]) - 97] = label
    return {"board": board, "reviewConfirmed": True, **details}


def create(client, data):
    response = client.post("/game/import", json=data)
    assert response.status_code == 200, response.text
    return response.json()


def move(client, game, source, target, token=None):
    response = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 8 - int(source[1]),
            "fromCol": ord(source[0]) - 97,
            "toRow": 8 - int(target[1]),
            "toCol": ord(target[0]) - 97,
            "expectedVersion": game["version"],
        },
        headers={"Authorization": f"Bearer {token}"} if token else {},
    )
    assert response.status_code == 200, response.text
    return response.json()


def targets(game, square):
    origin = {"row": 8 - int(square[1]), "col": ord(square[0]) - 97}
    return {
        f"{chr(97 + option['to']['col'])}{8 - option['to']['row']}"
        for option in game["validMoves"]
        if option["from"] == origin
    }


def test_import_preserves_side_and_counters_without_fake_history(client):
    game = create(client, payload(currentPlayer="black", fullmoveNumber=23, halfmoveClock=17))[
        "game"
    ]
    assert game["currentPlayer"] == "black"
    assert game["history"] == [] and game["score"] == {"white": 0, "black": 0}
    record = game_service.get_game(game["id"])
    assert classic_position_fen(record.state).endswith("b - - 17 23")
    restored = GameState.model_validate_json(record.state.model_dump_json())
    assert restored.imported_position.fullmove_number == 23
    updated = move(client, game, "e8", "d8")
    assert len(updated["history"]) == 1
    assert classic_position_fen(game_service.get_game(game["id"]).state).endswith("w - - 18 24")


def test_midgame_check_is_allowed_but_illegal_previous_side_is_rejected(client):
    data = payload({"e1": "white-king", "a8": "black-king", "e7": "black-rook"})
    game = create(client, data)["game"]
    assert game["gameStatus"] == "check"
    data["currentPlayer"] = "black"
    result = client.post("/game/import/validate", json=data).json()
    assert not result["valid"] and "just moved" in result["issues"][0]["message"]


def test_castling_is_opt_in_and_survives_reload(client):
    pieces = {"e1": "white-king", "e8": "black-king", "a1": "white-rook", "h1": "white-rook"}
    game = create(client, payload(pieces))["game"]
    assert "g1" not in targets(game, "e1") and "c1" not in targets(game, "e1")
    game = create(client, payload(pieces, castlingRights={"whiteKing": True}))["game"]
    reloaded = client.get(f"/game/{game['id']}").json()
    assert "g1" in targets(reloaded, "e1") and "c1" not in targets(reloaded, "e1")
    moved = move(client, reloaded, "e1", "g1")
    assert moved["board"][7][5]["type"] == "rook"
    invalid = client.post(
        "/game/import/validate", json=payload(castlingRights={"whiteKing": True})
    ).json()
    assert not invalid["valid"] and invalid["issues"][0]["field"] == "castlingRights"


def test_imported_en_passant_works_once_without_history_entry(client):
    pieces = {"e1": "white-king", "e8": "black-king", "e5": "white-pawn", "d5": "black-pawn"}
    data = payload(pieces, enPassant="d6", fullmoveNumber=15)
    game = create(client, data)["game"]
    assert "d6" in targets(game, "e5") and game["history"] == []
    assert " d6 " in classic_position_fen(game_service.get_game(game["id"]).state)
    captured = move(client, game, "e5", "d6")
    assert captured["board"][3][3] is None and captured["score"]["white"] == 1
    game = create(client, data)["game"]
    game = move(client, game, "e1", "f1")
    game = move(client, game, "e8", "f8")
    assert "d6" not in targets(game, "e5")
    invalid = client.post("/game/import/validate", json=payload(pieces, enPassant="d3")).json()
    assert not invalid["valid"]


def test_import_rejects_unreviewed_impossible_terminal_and_bot_positions(client):
    assert client.post("/game/import", json=payload(reviewConfirmed=False)).status_code == 400
    assert client.post("/game/import", json=payload(mode="bot")).status_code == 422
    assert (
        client.post("/game/import", json={**payload(), "board": [[None] * 7] * 8}).status_code
        == 422
    )
    assert client.post("/game/import", json=payload({"e1": "white-elephant"})).status_code == 422
    for pieces in [
        {"e1": "white-king", "e8": "black-king"},
        {"e1": "white-king", "e2": "black-king", "h2": "white-rook"},
        {"e1": "white-king", "a2": "white-king", "e8": "black-king", "h2": "white-rook"},
        {"e1": "white-king", "e8": "black-king", "a1": "white-pawn"},
        {"h1": "white-king", "f3": "black-king", "g2": "black-queen"},
    ]:
        assert client.post("/game/import", json=payload(pieces)).status_code == 400


def test_import_online_invite_uses_existing_seat_security_and_sync(client):
    host = create(client, payload(mode="online", currentPlayer="black"))
    assert not host["game"]["ready"] and host["inviteCode"]
    guest = client.post("/game/join", json={"inviteCode": host["inviteCode"]}).json()
    assert guest["playerColor"] == "black" and guest["game"]["currentPlayer"] == "black"
    assert client.get(f"/game/{host['game']['id']}").status_code == 401
    updated = move(client, guest["game"], "h7", "h5", guest["playerToken"])
    headers = {"Authorization": f"Bearer {host['playerToken']}"}
    assert (
        client.get(f"/game/{updated['id']}", headers=headers).json()["board"][3][7]["type"]
        == "pawn"
    )


def test_restart_restores_imported_position_and_rights(client):
    data = payload(currentPlayer="black", fullmoveNumber=12, halfmoveClock=6)
    game = create(client, data)["game"]
    game = move(client, game, "h7", "h5")
    route = f"/game/{game['id']}/rematch"
    proposal = client.post(
        route, json={"action": "request", "color": "white", "expectedVersion": game["version"]}
    ).json()
    reset = client.post(
        route, json={"action": "accept", "color": "black", "expectedVersion": proposal["version"]}
    )
    assert reset.status_code == 200, reset.text
    result = reset.json()
    assert result["currentPlayer"] == "black" and result["history"] == []
    assert result["board"][1][7]["type"] == "pawn"
    assert classic_position_fen(game_service.get_game(game["id"]).state).endswith("b - - 6 12")


def test_black_imported_en_passant_and_fifty_move_counter(client):
    pieces = {"e1": "white-king", "e8": "black-king", "d4": "white-pawn", "e4": "black-pawn"}
    game = create(client, payload(pieces, currentPlayer="black", enPassant="d3"))["game"]
    assert "d3" in targets(game, "e4")
    captured = move(client, game, "e4", "d3")
    assert captured["board"][4][3] is None and captured["score"]["black"] == 1
    game = create(client, payload(halfmoveClock=99))["game"]
    finished = move(client, game, "e1", "d1")
    assert finished["phase"] == "finished"
    assert finished["result"]["reasonCode"] == "fifty_move_rule"


def test_blocked_castling_retains_history_rights_and_layout_is_immutable(client):
    pieces = {
        "e1": "white-king",
        "e8": "black-king",
        "h1": "white-rook",
        "g1": "white-knight",
        "a3": "white-pawn",
    }
    game = create(client, payload(pieces, castlingRights={"whiteKing": True}))["game"]
    assert "g1" not in targets(game, "e1")
    assert " K " in classic_position_fen(game_service.get_game(game["id"]).state)
    assert "a5" not in targets(game, "a3")
    response = client.post(
        f"/game/{game['id']}/layout", json={"placements": [], "expectedVersion": game["version"]}
    )
    assert response.status_code == 409
