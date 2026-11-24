from __future__ import annotations


def timed_game(client, increment: int) -> dict:
    response = client.post(
        "/game/create",
        json={
            "mode": "local",
            "configuration": {"victory": {"mode": "timed", "timeSeconds": 300, "incrementSeconds": increment}},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["game"]


def test_each_completed_turn_adds_the_increment_to_the_mover(client):
    game = timed_game(client, 5)
    assert game["clock"]["incrementSeconds"] == 5
    assert game["configuration"]["victory"]["incrementSeconds"] == 5
    moved = client.post(
        f"/game/{game['id']}/move",
        json={"fromRow": 6, "fromCol": 4, "toRow": 4, "toCol": 4},
    ).json()
    clock = moved["clock"]
    assert clock["activeColor"] == "black"
    assert 300 < clock["remainingSeconds"]["white"] <= 305
    assert clock["remainingSeconds"]["black"] <= 300


def test_sudden_death_games_add_nothing(client):
    game = timed_game(client, 0)
    moved = client.post(
        f"/game/{game['id']}/move",
        json={"fromRow": 6, "fromCol": 4, "toRow": 4, "toCol": 4},
    ).json()
    assert moved["clock"]["remainingSeconds"]["white"] <= 300


def test_increment_is_bounded(client):
    response = client.post(
        "/game/validate",
        json={"mode": "local", "configuration": {"victory": {"mode": "timed", "incrementSeconds": 61}}},
    )
    assert response.status_code == 422
