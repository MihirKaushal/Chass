from __future__ import annotations


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_online_game(client) -> dict:
    response = client.post(
        "/game/create",
        json={
            "mode": "online",
            "boardRows": 8,
            "boardCols": 8,
            "rules": [],
            "customPieces": [],
        },
    )
    assert response.status_code == 200
    return response.json()


def test_local_game_remains_token_free(client):
    created = client.post("/game/create", json={"mode": "local"})

    assert created.status_code == 200
    session = created.json()
    game = session["game"]
    assert session["role"] == "local"
    assert session["playerToken"] is None
    assert game["mode"] == "local"
    assert game["ready"] is True
    assert game["version"] == 1

    moved = client.post(
        f"/game/{game['id']}/move",
        json={"fromRow": 6, "fromCol": 4, "toRow": 4, "toCol": 4},
    )
    assert moved.status_code == 200
    assert moved.json()["version"] == 2
    assert moved.json()["currentPlayer"] == "black"

    loaded = client.get(f"/game/{game['id']}")
    assert loaded.status_code == 200
    assert loaded.json()["version"] == 2


def test_online_invite_and_seat_authorization(client):
    created = create_online_game(client)
    game = created["game"]
    host_token = created["playerToken"]

    assert created["playerColor"] == "white"
    assert created["role"] == "host"
    assert created["inviteToken"] not in str(game)
    assert game["ready"] is False
    assert game["players"] == {"white": "joined", "black": "open"}

    assert client.get(f"/game/{game['id']}").status_code == 401

    waiting_move = client.post(
        f"/game/{game['id']}/move",
        headers=auth(host_token),
        json={
            "fromRow": 6,
            "fromCol": 4,
            "toRow": 4,
            "toCol": 4,
            "expectedVersion": 1,
        },
    )
    assert waiting_move.status_code == 409

    joined = client.post(
        "/game/join",
        json={"inviteToken": created["inviteToken"]},
    )
    assert joined.status_code == 200
    black_session = joined.json()
    assert black_session["playerColor"] == "black"
    assert black_session["game"]["ready"] is True

    reused = client.post(
        "/game/join",
        json={"inviteToken": created["inviteToken"]},
    )
    assert reused.status_code == 409

    black_moves_white = client.post(
        f"/game/{game['id']}/move",
        headers=auth(black_session["playerToken"]),
        json={
            "fromRow": 6,
            "fromCol": 4,
            "toRow": 4,
            "toCol": 4,
            "expectedVersion": 1,
        },
    )
    assert black_moves_white.status_code == 403

    white_move = client.post(
        f"/game/{game['id']}/move",
        headers=auth(host_token),
        json={
            "fromRow": 6,
            "fromCol": 4,
            "toRow": 4,
            "toCol": 4,
            "expectedVersion": 1,
        },
    )
    assert white_move.status_code == 200
    assert white_move.json()["version"] == 2

    stale_black_move = client.post(
        f"/game/{game['id']}/move",
        headers=auth(black_session["playerToken"]),
        json={
            "fromRow": 1,
            "fromCol": 4,
            "toRow": 3,
            "toCol": 4,
            "expectedVersion": 1,
        },
    )
    assert stale_black_move.status_code == 409

    black_move = client.post(
        f"/game/{game['id']}/move",
        headers=auth(black_session["playerToken"]),
        json={
            "fromRow": 1,
            "fromCol": 4,
            "toRow": 3,
            "toCol": 4,
            "expectedVersion": 2,
        },
    )
    assert black_move.status_code == 200
    assert black_move.json()["version"] == 3
    assert black_move.json()["currentPlayer"] == "white"


def test_only_host_can_customize_online_game(client):
    created = create_online_game(client)
    game_id = created["game"]["id"]
    host_token = created["playerToken"]
    joined = client.post(
        "/game/join",
        json={"inviteToken": created["inviteToken"]},
    ).json()

    guest_change = client.post(
        f"/game/{game_id}/rules",
        headers=auth(joined["playerToken"]),
        json={
            "expectedVersion": 1,
            "rules": [{"id": "score_target_win", "enabled": True}],
        },
    )
    assert guest_change.status_code == 403

    host_change = client.post(
        f"/game/{game_id}/rules",
        headers=auth(host_token),
        json={
            "expectedVersion": 1,
            "rules": [
                {
                    "id": "score_target_win",
                    "enabled": True,
                    "params": {"targetScore": 21},
                }
            ],
        },
    )
    assert host_change.status_code == 200
    assert host_change.json()["version"] == 2
    target_rule = next(
        rule for rule in host_change.json()["rules"] if rule["id"] == "score_target_win"
    )
    assert target_rule["enabled"] is True
    assert target_rule["params"]["targetScore"] == 21

    full_game_invite = client.post(
        f"/game/{game_id}/invite",
        headers=auth(host_token),
    )
    assert full_game_invite.status_code == 409


def test_host_can_replace_unused_invite(client):
    created = create_online_game(client)
    game_id = created["game"]["id"]

    replacement = client.post(
        f"/game/{game_id}/invite",
        headers=auth(created["playerToken"]),
    )
    assert replacement.status_code == 200
    next_invite = replacement.json()
    assert next_invite["inviteToken"] != created["inviteToken"]
    assert "/join/" in next_invite["inviteUrl"]

    old_join = client.post("/game/join", json={"inviteToken": created["inviteToken"]})
    assert old_join.status_code == 409
    assert "replaced" in old_join.json()["detail"].lower()

    new_join = client.post("/game/join", json={"inviteToken": next_invite["inviteToken"]})
    assert new_join.status_code == 200


def test_websocket_authenticates_before_joining_room(client):
    created = create_online_game(client)
    game_id = created["game"]["id"]

    with client.websocket_connect(f"/game/ws/{game_id}") as websocket:
        websocket.send_json(
            {
                "type": "authenticate",
                "token": created["playerToken"],
            }
        )
        initial = websocket.receive_json()
        assert initial["type"] == "game_state"
        assert initial["game"]["id"] == game_id
        assert initial["game"]["version"] == 1

        presence = websocket.receive_json()
        assert presence["type"] == "presence"
        assert presence["connected"]["white"] is True
