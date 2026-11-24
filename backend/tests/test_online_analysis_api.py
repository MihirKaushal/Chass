from __future__ import annotations

from backend.routes.game import LIVE_ONLINE_ANALYSIS_REASON


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def online_game(client) -> tuple[dict, dict]:
    created = client.post("/game/create", json={"mode": "online"}).json()
    joined = client.post("/game/join", json={"inviteCode": created["inviteCode"]}).json()
    return created, joined


def test_online_analysis_is_withheld_until_the_game_ends(client):
    created, joined = online_game(client)
    game_id = created["game"]["id"]
    for token in (created["playerToken"], joined["playerToken"]):
        live = client.get(f"/game/{game_id}/analysis", headers=auth(token)).json()
        assert live["status"] == "withheld"
        assert live["reason"] == LIVE_ONLINE_ANALYSIS_REASON
        assert live.get("evaluation") is None and live.get("factors") in (None, [])

    client.post(
        f"/game/{game_id}/resign",
        headers=auth(joined["playerToken"]),
        json={"expectedVersion": joined["game"]["version"]},
    )
    finished = client.get(f"/game/{game_id}/analysis", headers=auth(created["playerToken"]))
    assert finished.json()["reason"] != LIVE_ONLINE_ANALYSIS_REASON


def test_local_analysis_is_not_withheld(client):
    game = client.post("/game/create", json={"mode": "local"}).json()["game"]
    analysis = client.get(f"/game/{game['id']}/analysis").json()
    assert analysis["reason"] != LIVE_ONLINE_ANALYSIS_REASON
