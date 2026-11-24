from __future__ import annotations

from backend.routes.game import game_service
from backend.services.game_service import MAX_UNDO_SNAPSHOTS


def local_game(client, **configuration) -> dict:
    payload = {"mode": "local"}
    if configuration:
        payload["configuration"] = configuration
    return client.post("/game/create", json=payload).json()["game"]


def move(client, game_id, frm, to, headers=None, version=None):
    body = {"fromRow": frm[0], "fromCol": frm[1], "toRow": to[0], "toCol": to[1]}
    if version is not None:
        body["expectedVersion"] = version
    response = client.post(f"/game/{game_id}/move", json=body, headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()


def test_local_takeback_restores_the_previous_position(client):
    game = local_game(client)
    assert game["takebackAvailable"] is False
    after_e4 = move(client, game["id"], (6, 4), (4, 4))
    assert after_e4["takebackAvailable"] is True
    after_e5 = move(client, game["id"], (1, 4), (3, 4))

    undone = client.post(f"/game/{game['id']}/takeback", json={})
    assert undone.status_code == 200
    body = undone.json()
    assert body["lastMoveExplanation"] == "Took back the last move."
    assert body["currentPlayer"] == "black"
    assert body["board"][3][4] is None
    assert body["board"][1][4]["type"] == "pawn"
    assert body["version"] == after_e5["version"] + 1
    assert [entry["moveNumber"] for entry in body["history"]] == [1]

    replayed = move(client, game["id"], (1, 3), (3, 3))
    assert [entry["moveNumber"] for entry in replayed["history"]] == [1, 2]


def test_takebacks_are_bounded_and_run_out(client):
    game = local_game(client)
    moves = [((6, 0), (5, 0)), ((1, 0), (2, 0)), ((6, 1), (5, 1)),
             ((1, 1), (2, 1)), ((6, 2), (5, 2)), ((1, 2), (2, 2))]
    for frm, to in moves:
        move(client, game["id"], frm, to)
    record = game_service.get_game(game["id"])
    assert len(record.state.undo_snapshots) == MAX_UNDO_SNAPSHOTS
    for _ in range(MAX_UNDO_SNAPSHOTS):
        assert client.post(f"/game/{game['id']}/takeback", json={}).status_code == 200
    exhausted = client.post(f"/game/{game['id']}/takeback", json={})
    assert exhausted.status_code == 409
    assert client.get(f"/game/{game['id']}").json()["takebackAvailable"] is False


def test_a_finished_game_can_take_back_the_final_move(client):
    game = local_game(client)
    for frm, to in [((6, 5), (5, 5)), ((1, 4), (3, 4)), ((6, 6), (4, 6))]:
        move(client, game["id"], frm, to)
    mated = move(client, game["id"], (0, 3), (4, 7))  # Fool's mate
    assert mated["gameStatus"] == "checkmate"
    undone = client.post(f"/game/{game['id']}/takeback", json={}).json()
    assert undone["phase"] == "play"
    assert undone["gameStatus"] == "active"
    assert undone["currentPlayer"] == "black"


def test_timed_takeback_restores_clock_times(client):
    game = local_game(client, victory={"mode": "timed", "timeSeconds": 300})
    move(client, game["id"], (6, 4), (4, 4))
    undone = client.post(f"/game/{game['id']}/takeback", json={}).json()
    assert undone["clock"]["activeColor"] == "white"
    # White's time used before the move stays spent; Black's clock is untouched.
    assert 299 < undone["clock"]["remainingSeconds"]["white"] <= 300
    assert undone["clock"]["remainingSeconds"]["black"] == 300


def test_online_games_do_not_allow_takebacks(client):
    created = client.post("/game/create", json={"mode": "online"}).json()
    joined = client.post("/game/join", json={"inviteCode": created["inviteCode"]}).json()
    headers = {"Authorization": f"Bearer {created['playerToken']}"}
    played = move(client, created["game"]["id"], (6, 4), (4, 4), headers, joined["game"]["version"])
    assert played["takebackAvailable"] is False
    response = client.post(
        f"/game/{created['game']['id']}/takeback",
        headers=headers,
        json={"expectedVersion": played["version"]},
    )
    assert response.status_code == 409
    assert game_service.get_game(created["game"]["id"], created["playerToken"]).state.undo_snapshots == []


def test_a_restart_clears_earlier_positions(client):
    game = local_game(client)
    move(client, game["id"], (6, 4), (4, 4))
    client.post(f"/game/{game['id']}/rematch", json={"action": "request", "color": "white"})
    restarted = client.post(
        f"/game/{game['id']}/rematch", json={"action": "accept", "color": "black"}
    ).json()
    assert restarted["history"] == []
    assert restarted["takebackAvailable"] is False


def test_engine_clones_never_copy_snapshots(client):
    game = local_game(client)
    move(client, game["id"], (6, 4), (4, 4))
    state = game_service.get_game(game["id"]).state
    assert state.undo_snapshots
    clone = state.clone()
    assert clone.undo_snapshots == []
    assert state.undo_snapshots


def test_bot_takeback_also_undoes_the_bot_reply(client):
    import time

    created = client.post(
        "/game/create",
        json={
            "mode": "bot",
            "bot": {"profileId": "chass-500", "humanColor": "white"},
            "rules": [{"id": "double_capture_rook", "enabled": True}],
        },
    ).json()
    game_id = created["game"]["id"]
    move(client, game_id, (6, 4), (4, 4), version=created["game"]["version"])

    deadline = time.monotonic() + 10
    latest = client.get(f"/game/{game_id}").json()
    while len(latest["history"]) < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
        latest = client.get(f"/game/{game_id}").json()
    assert len(latest["history"]) == 2, latest["history"]
    assert latest["currentPlayer"] == "white"
    assert latest["takebackAvailable"] is True

    undone = client.post(
        f"/game/{game_id}/takeback", json={"expectedVersion": latest["version"]}
    ).json()
    assert undone["lastMoveExplanation"] == "Took back the last 2 moves."
    assert undone["history"] == []
    assert undone["currentPlayer"] == "white"
    assert undone["board"][6][4]["type"] == "pawn"
    assert undone["takebackAvailable"] is False
