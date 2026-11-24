from __future__ import annotations


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def online_game(client) -> tuple[str, str, str, int]:
    created = client.post("/game/create", json={"mode": "online"}).json()
    joined = client.post("/game/join", json={"inviteCode": created["inviteCode"]}).json()
    return created["game"]["id"], created["playerToken"], joined["playerToken"], joined["game"]["version"]


def draw(client, game_id, token, action, version):
    return client.post(
        f"/game/{game_id}/draw",
        headers=auth(token),
        json={"action": action, "expectedVersion": version},
    )


def test_online_draw_offer_can_be_accepted(client):
    game_id, white, black, version = online_game(client)
    offered = draw(client, game_id, white, "offer", version)
    assert offered.status_code == 200
    assert offered.json()["drawOfferedBy"] == "white"
    black_view = client.get(f"/game/{game_id}", headers=auth(black)).json()
    assert black_view["drawOfferedBy"] == "white"

    # The offering player cannot accept their own offer.
    assert draw(client, game_id, white, "accept", offered.json()["version"]).status_code == 409

    accepted = draw(client, game_id, black, "accept", offered.json()["version"])
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["phase"] == "finished"
    assert body["gameStatus"] == "draw"
    assert body["winner"] is None
    assert body["result"]["reasonCode"] == "draw_agreement"
    assert body["drawOfferedBy"] is None


def test_draw_offers_can_be_declined_or_withdrawn(client):
    game_id, white, black, version = online_game(client)
    version = draw(client, game_id, white, "offer", version).json()["version"]
    assert draw(client, game_id, white, "offer", version).status_code == 409
    assert draw(client, game_id, black, "cancel", version).status_code == 409
    declined = draw(client, game_id, black, "decline", version)
    assert declined.status_code == 200
    assert declined.json()["drawOfferedBy"] is None
    assert declined.json()["phase"] == "play"

    version = draw(client, game_id, black, "offer", declined.json()["version"]).json()["version"]
    withdrawn = draw(client, game_id, black, "cancel", version)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["drawOfferedBy"] is None


def test_an_offer_stands_until_the_opponent_moves(client):
    game_id, white, black, version = online_game(client)
    version = draw(client, game_id, white, "offer", version).json()["version"]
    own_move = client.post(
        f"/game/{game_id}/move",
        headers=auth(white),
        json={"fromRow": 6, "fromCol": 4, "toRow": 4, "toCol": 4, "expectedVersion": version},
    )
    assert own_move.status_code == 200
    assert own_move.json()["drawOfferedBy"] == "white"

    reply = client.post(
        f"/game/{game_id}/move",
        headers=auth(black),
        json={
            "fromRow": 1, "fromCol": 4, "toRow": 3, "toCol": 4,
            "expectedVersion": own_move.json()["version"],
        },
    )
    assert reply.status_code == 200
    assert reply.json()["drawOfferedBy"] is None


def test_local_draw_names_the_acting_side(client):
    game_id = client.post("/game/create", json={"mode": "local"}).json()["game"]["id"]
    assert client.post(f"/game/{game_id}/draw", json={"action": "offer"}).status_code == 400
    offered = client.post(f"/game/{game_id}/draw", json={"action": "offer", "color": "white"})
    assert offered.json()["drawOfferedBy"] == "white"
    accepted = client.post(f"/game/{game_id}/draw", json={"action": "accept", "color": "black"})
    assert accepted.json()["gameStatus"] == "draw"


def test_bot_games_do_not_take_draw_offers(client):
    created = client.post(
        "/game/create",
        json={
            "mode": "bot",
            "bot": {"profileId": "chass-500", "humanColor": "white"},
            "rules": [{"id": "double_capture_rook", "enabled": True}],
        },
    ).json()
    response = client.post(
        f"/game/{created['game']['id']}/draw",
        json={"action": "offer", "expectedVersion": created["game"]["version"]},
    )
    assert response.status_code == 409
