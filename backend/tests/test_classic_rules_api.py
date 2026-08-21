from __future__ import annotations

from backend.routes.game import game_service


def configured_game(initial_layout: list[dict], *, victory_mode: str = "checkmate") -> dict:
    return {
        "mode": "local",
        "boardRows": 8,
        "boardCols": 8,
        "configuration": {
            "schemaVersion": 2,
            "presetId": "classic-rules-test",
            "formationId": "custom",
            "enabledPieces": ["pawn", "knight", "bishop", "rook", "queen", "king"],
            "piecePoints": {
                "pawn": 1,
                "knight": 3,
                "bishop": 3,
                "rook": 5,
                "queen": 9,
                "king": 0,
            },
            "initialLayout": initial_layout,
            "victory": {"mode": victory_mode},
            "specialAbilities": {"enabled": False, "allowed": []},
            "gambit": {"enabled": False},
        },
    }


def create_game(client, layout: list[dict], *, victory_mode: str = "checkmate") -> dict:
    response = client.post(
        "/game/create",
        json=configured_game(layout, victory_mode=victory_mode),
    )
    assert response.status_code == 200, response.text
    return response.json()["game"]


def move(client, game: dict, source: tuple[int, int], target: tuple[int, int]) -> dict:
    response = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": source[0],
            "fromCol": source[1],
            "toRow": target[0],
            "toCol": target[1],
            "expectedVersion": game["version"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def targets(game: dict, source: tuple[int, int]) -> set[tuple[int, int]]:
    return {
        (option["to"]["row"], option["to"]["col"])
        for option in game["validMoves"]
        if option["from"] == {"row": source[0], "col": source[1]}
    }


def test_castling_moves_the_king_and_rook_on_both_sides(client):
    layout = [
        {"row": 7, "col": 4, "type": "king", "color": "white"},
        {"row": 7, "col": 0, "type": "rook", "color": "white"},
        {"row": 7, "col": 7, "type": "rook", "color": "white"},
        {"row": 0, "col": 4, "type": "king", "color": "black"},
        {"row": 0, "col": 0, "type": "rook", "color": "black"},
        {"row": 0, "col": 7, "type": "rook", "color": "black"},
    ]
    kingside = create_game(client, layout)
    assert {(7, 2), (7, 6)} <= targets(kingside, (7, 4))

    kingside = move(client, kingside, (7, 4), (7, 6))
    assert kingside["board"][7][6]["type"] == "king"
    assert kingside["board"][7][5]["type"] == "rook"
    assert kingside["board"][7][7] is None
    assert "castled kingside" in kingside["history"][-1]["explanation"].lower()

    queenside = create_game(client, layout)
    queenside = move(client, queenside, (7, 4), (7, 2))
    assert queenside["board"][7][2]["type"] == "king"
    assert queenside["board"][7][3]["type"] == "rook"
    assert queenside["board"][7][0] is None
    assert "castled queenside" in queenside["history"][-1]["explanation"].lower()


def test_castling_rejects_attacked_path_and_moved_rook(client):
    attacked = create_game(
        client,
        [
            {"row": 7, "col": 4, "type": "king", "color": "white"},
            {"row": 7, "col": 7, "type": "rook", "color": "white"},
            {"row": 0, "col": 0, "type": "king", "color": "black"},
            {"row": 0, "col": 5, "type": "rook", "color": "black"},
        ],
    )
    assert (7, 6) not in targets(attacked, (7, 4))

    moved_rook = create_game(
        client,
        [
            {"row": 7, "col": 4, "type": "king", "color": "white"},
            {"row": 7, "col": 7, "type": "rook", "color": "white"},
            {"row": 0, "col": 0, "type": "king", "color": "black"},
            {"row": 0, "col": 7, "type": "rook", "color": "black"},
        ],
    )
    moved_rook = move(client, moved_rook, (7, 7), (6, 7))
    moved_rook = move(client, moved_rook, (0, 0), (0, 1))
    moved_rook = move(client, moved_rook, (6, 7), (7, 7))
    moved_rook = move(client, moved_rook, (0, 1), (0, 0))
    assert (7, 6) not in targets(moved_rook, (7, 4))


def test_en_passant_is_immediate_and_removes_the_passed_pawn(client):
    game = create_game(
        client,
        [
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 3, "col": 4, "type": "pawn", "color": "white"},
            {"row": 1, "col": 3, "type": "pawn", "color": "black"},
            {"row": 7, "col": 0, "type": "rook", "color": "white"},
            {"row": 0, "col": 0, "type": "rook", "color": "black"},
        ],
    )
    game = move(client, game, (7, 7), (7, 6))
    game = move(client, game, (1, 3), (3, 3))
    assert (2, 3) in targets(game, (3, 4))

    game = move(client, game, (3, 4), (2, 3))
    assert game["board"][2][3]["type"] == "pawn"
    assert game["board"][3][3] is None
    assert game["capturedPieces"]["white"][-1]["type"] == "pawn"
    assert "en passant" in game["history"][-1]["explanation"].lower()


def test_en_passant_expires_after_one_reply(client):
    game = create_game(
        client,
        [
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 3, "col": 4, "type": "pawn", "color": "white"},
            {"row": 1, "col": 3, "type": "pawn", "color": "black"},
            {"row": 7, "col": 0, "type": "rook", "color": "white"},
            {"row": 0, "col": 0, "type": "rook", "color": "black"},
        ],
    )
    game = move(client, game, (7, 7), (7, 6))
    game = move(client, game, (1, 3), (3, 3))
    game = move(client, game, (7, 0), (6, 0))
    game = move(client, game, (0, 7), (0, 6))
    assert (2, 3) not in targets(game, (3, 4))


def test_insufficient_material_draws_only_for_dead_positions(client):
    cases = [
        [{"row": 6, "col": 2, "type": "bishop", "color": "white"}],
        [{"row": 6, "col": 2, "type": "knight", "color": "white"}],
        [
            {"row": 6, "col": 2, "type": "bishop", "color": "white"},
            {"row": 1, "col": 5, "type": "bishop", "color": "black"},
        ],
    ]
    kings = [
        {"row": 7, "col": 7, "type": "king", "color": "white"},
        {"row": 0, "col": 0, "type": "king", "color": "black"},
    ]
    for material in cases:
        game = create_game(client, [*kings, *material])
        assert game["gameStatus"] == "draw"
        assert game["result"]["reasonCode"] == "insufficient_material"

    opposite_bishops = create_game(
        client,
        [
            *kings,
            {"row": 6, "col": 2, "type": "bishop", "color": "white"},
            {"row": 1, "col": 4, "type": "bishop", "color": "black"},
        ],
    )
    assert opposite_bishops["gameStatus"] == "active"

    rook_material = create_game(
        client,
        [*kings, {"row": 6, "col": 2, "type": "rook", "color": "white"}],
    )
    assert rook_material["gameStatus"] == "active"


def test_threefold_repetition_ends_the_game(client):
    game = create_game(
        client,
        [
            {"row": 7, "col": 7, "type": "king", "color": "white"},
            {"row": 0, "col": 7, "type": "king", "color": "black"},
            {"row": 7, "col": 1, "type": "knight", "color": "white"},
            {"row": 0, "col": 1, "type": "knight", "color": "black"},
        ],
    )
    cycle = [
        ((7, 1), (5, 0)),
        ((0, 1), (2, 0)),
        ((5, 0), (7, 1)),
        ((2, 0), (0, 1)),
    ]
    for _ in range(2):
        for source, target in cycle:
            game = move(client, game, source, target)

    assert game["gameStatus"] == "draw"
    assert game["result"]["reasonCode"] == "threefold_repetition"


def test_fifty_move_rule_and_pawn_reset(client):
    layout = [
        {"row": 7, "col": 7, "type": "king", "color": "white"},
        {"row": 0, "col": 7, "type": "king", "color": "black"},
        {"row": 7, "col": 0, "type": "rook", "color": "white"},
        {"row": 0, "col": 0, "type": "rook", "color": "black"},
    ]
    game = create_game(client, layout)
    record = game_service.repository.get_game(game["id"])
    assert record is not None
    record.state.classic.halfmove_clock = 99
    saved = game_service.repository.save_game(record.state, record.version)
    game["version"] = saved.version
    game = move(client, game, (7, 0), (6, 0))
    assert game["gameStatus"] == "draw"
    assert game["result"]["reasonCode"] == "fifty_move_rule"

    pawn_game = create_game(
        client,
        [
            *layout,
            {"row": 6, "col": 4, "type": "pawn", "color": "white"},
            {"row": 1, "col": 4, "type": "pawn", "color": "black"},
        ],
    )
    record = game_service.repository.get_game(pawn_game["id"])
    assert record is not None
    record.state.classic.halfmove_clock = 99
    saved = game_service.repository.save_game(record.state, record.version)
    pawn_game["version"] = saved.version
    pawn_game = move(client, pawn_game, (6, 4), (5, 4))
    assert pawn_game["gameStatus"] == "active"
    updated = game_service.repository.get_game(pawn_game["id"])
    assert updated is not None
    assert updated.state.classic.halfmove_clock == 0


def test_serialization_reuses_legal_moves_for_the_same_game_version(client, monkeypatch):
    game = client.post("/game/create", json={"mode": "local"}).json()["game"]
    record = game_service.repository.get_game(game["id"])
    assert record is not None

    with game_service._valid_moves_cache_lock:
        game_service._valid_moves_cache.clear()

    calls = 0
    original = game_service.engine.get_valid_moves_for_current_player

    def counted(state):
        nonlocal calls
        calls += 1
        return original(state)

    monkeypatch.setattr(
        game_service.engine,
        "get_valid_moves_for_current_player",
        counted,
    )
    game_service.serialize_game(record)
    game_service.serialize_game(record)

    assert calls == 1
