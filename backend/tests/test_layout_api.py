from __future__ import annotations


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def compact_layout() -> list[dict]:
    return [
        {"row": 3, "col": 2, "type": "king", "color": "white"},
        {"row": 3, "col": 0, "type": "rook", "color": "white"},
        {"row": 0, "col": 2, "type": "king", "color": "black"},
        {"row": 0, "col": 0, "type": "rook", "color": "black"},
    ]


def test_layout_rejects_duplicate_squares_without_mutating_game(client):
    game = client.post("/game/create", json={"mode": "local"}).json()["game"]
    response = client.post(
        f"/game/{game['id']}/layout",
        json={
            "placements": [
                {"row": 7, "col": 4, "type": "king", "color": "white"},
                {"row": 7, "col": 4, "type": "rook", "color": "white"},
                {"row": 0, "col": 4, "type": "king", "color": "black"},
            ],
            "expectedVersion": game["version"],
        },
    )

    assert response.status_code == 400
    assert "Only one piece" in response.json()["detail"]
    unchanged = client.get(f"/game/{game['id']}").json()
    assert unchanged["version"] == game["version"]
    assert unchanged["boardRows"] == 8


def test_layout_requires_exactly_one_king_per_player(client):
    game = client.post("/game/create", json={"mode": "local"}).json()["game"]
    response = client.post(
        f"/game/{game['id']}/layout",
        json={
            "placements": [
                {"row": 7, "col": 4, "type": "king", "color": "white"},
                {"row": 7, "col": 0, "type": "rook", "color": "white"},
            ],
            "expectedVersion": game["version"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Black must begin with exactly one King."


def test_resized_layout_becomes_the_rematch_source(client):
    game = client.post("/game/create", json={"mode": "local"}).json()["game"]
    updated_response = client.post(
        f"/game/{game['id']}/layout",
        json={
            "boardRows": 4,
            "boardCols": 4,
            "placements": compact_layout(),
            "expectedVersion": game["version"],
        },
    )
    assert updated_response.status_code == 200, updated_response.text
    updated = updated_response.json()
    assert updated["boardRows"] == 4
    assert updated["boardCols"] == 4
    assert updated["configuration"]["presetId"] == "custom"
    assert updated["configuration"]["formationId"] == "custom"
    assert updated["configuration"]["initialLayout"] == compact_layout()

    requested = client.post(
        f"/game/{game['id']}/rematch",
        json={
            "action": "request",
            "color": "white",
            "expectedVersion": updated["version"],
        },
    ).json()
    accepted_response = client.post(
        f"/game/{game['id']}/rematch",
        json={
            "action": "accept",
            "color": "black",
            "expectedVersion": requested["version"],
        },
    )

    assert accepted_response.status_code == 200, accepted_response.text
    restarted = accepted_response.json()
    assert restarted["boardRows"] == 4
    assert restarted["boardCols"] == 4
    assert restarted["board"][3][2]["type"] == "king"
    assert restarted["board"][0][0]["type"] == "rook"
    assert restarted["history"] == []


def test_layout_cannot_replace_a_game_after_play_begins(client):
    game = client.post("/game/create", json={"mode": "local"}).json()["game"]
    moved = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 6,
            "fromCol": 4,
            "toRow": 4,
            "toCol": 4,
            "expectedVersion": game["version"],
        },
    ).json()

    response = client.post(
        f"/game/{game['id']}/layout",
        json={
            "placements": compact_layout(),
            "expectedVersion": moved["version"],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "The starting layout cannot be changed after play begins."


def test_online_layout_locks_when_opponent_joins(client):
    created = client.post("/game/create", json={"mode": "online"}).json()
    joined = client.post(
        "/game/join",
        json={"inviteToken": created["inviteToken"]},
    ).json()

    response = client.post(
        f"/game/{created['game']['id']}/layout",
        headers=auth(created["playerToken"]),
        json={
            "boardRows": 4,
            "boardCols": 4,
            "placements": compact_layout(),
            "expectedVersion": joined["game"]["version"],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "The starting layout cannot be changed after an opponent joins."
    )
