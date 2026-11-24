from __future__ import annotations

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_standard_local_games_export_fen(client):
    game = client.post("/game/create", json={"mode": "local"}).json()["game"]
    assert game["fen"] == START_FEN
    moved = client.post(
        f"/game/{game['id']}/move",
        json={"fromRow": 6, "fromCol": 4, "toRow": 4, "toCol": 4},
    ).json()
    assert moved["fen"].startswith("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq")


def test_variants_do_not_export_fen(client):
    game = client.post(
        "/game/create", json={"mode": "local", "boardRows": 10, "boardCols": 10}
    ).json()["game"]
    assert game["fen"] is None


def test_live_online_games_hide_fen_until_the_end(client):
    created = client.post("/game/create", json={"mode": "online"}).json()
    joined = client.post("/game/join", json={"inviteCode": created["inviteCode"]}).json()
    assert joined["game"]["fen"] is None
    resigned = client.post(
        f"/game/{created['game']['id']}/resign",
        headers=auth(joined["playerToken"]),
        json={"expectedVersion": joined["game"]["version"]},
    ).json()
    assert resigned["fen"] == START_FEN
