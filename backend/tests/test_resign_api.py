from __future__ import annotations


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def online_game(client) -> tuple[dict, dict]:
    created = client.post("/game/create", json={"mode": "online"}).json()
    joined = client.post("/game/join", json={"inviteCode": created["inviteCode"]}).json()
    return created, joined


def test_local_resignation_names_the_side_and_ends_the_game(client):
    game = client.post("/game/create", json={"mode": "local"}).json()["game"]
    missing = client.post(f"/game/{game['id']}/resign", json={})
    assert missing.status_code == 400

    resigned = client.post(f"/game/{game['id']}/resign", json={"color": "white"})
    assert resigned.status_code == 200
    body = resigned.json()
    assert body["phase"] == "finished"
    assert body["gameStatus"] == "resigned"
    assert body["winner"] == "black"
    assert body["result"]["reasonCode"] == "resignation"
    assert body["result"]["description"] == "Black won! White resigned."
    assert body["validMoves"] == []

    again = client.post(f"/game/{game['id']}/resign", json={"color": "black"})
    assert again.status_code == 409
    move = client.post(
        f"/game/{game['id']}/move",
        json={"fromRow": 6, "fromCol": 4, "toRow": 4, "toCol": 4},
    )
    assert move.status_code == 409


def test_online_players_can_only_resign_their_own_seat(client):
    created, joined = online_game(client)
    game_id = created["game"]["id"]
    version = joined["game"]["version"]

    assert client.post(
        f"/game/{game_id}/resign", json={"color": "white", "expectedVersion": version}
    ).status_code == 401

    # A remote player resigns their own seat even if they name the other color.
    resigned = client.post(
        f"/game/{game_id}/resign",
        headers=auth(joined["playerToken"]),
        json={"color": "white", "expectedVersion": version},
    )
    assert resigned.status_code == 200
    assert resigned.json()["winner"] == "white"

    host_view = client.get(f"/game/{game_id}", headers=auth(created["playerToken"])).json()
    assert host_view["gameStatus"] == "resigned"
    assert host_view["result"]["description"] == "White won! Black resigned."


def test_online_resignation_requires_the_current_version(client):
    created, joined = online_game(client)
    response = client.post(
        f"/game/{created['game']['id']}/resign",
        headers=auth(created["playerToken"]),
        json={"expectedVersion": joined["game"]["version"] + 1},
    )
    assert response.status_code == 409


def test_resigning_waits_for_play_to_begin(client):
    created = client.post("/game/create", json={"mode": "online"}).json()
    response = client.post(
        f"/game/{created['game']['id']}/resign",
        headers=auth(created["playerToken"]),
        json={"expectedVersion": created["game"]["version"]},
    )
    assert response.status_code == 409


def test_bot_game_human_resigns(client):
    created = client.post(
        "/game/create",
        json={
            "mode": "bot",
            "configuration": {"specialAbilities": {"enabled": False}},
            "bot": {"profileId": "chass-500", "humanColor": "white"},
            "rules": [{"id": "double_capture_rook", "enabled": True}],
        },
    )
    assert created.status_code == 200, created.text
    game = created.json()["game"]
    resigned = client.post(
        f"/game/{game['id']}/resign",
        json={"color": "black", "expectedVersion": game["version"]},
    )
    assert resigned.status_code == 200
    assert resigned.json()["winner"] == "black"
    assert resigned.json()["result"]["description"] == "Black won! White resigned."


def test_timed_resignation_charges_the_running_clock(client):
    game = client.post(
        "/game/create",
        json={"mode": "local", "configuration": {"victory": {"mode": "timed", "timeSeconds": 300}}},
    ).json()["game"]
    resigned = client.post(f"/game/{game['id']}/resign", json={"color": "white"})
    assert resigned.status_code == 200
    clock = resigned.json()["clock"]
    assert clock["remainingSeconds"]["white"] <= 300
    assert clock["remainingSeconds"]["black"] == 300
