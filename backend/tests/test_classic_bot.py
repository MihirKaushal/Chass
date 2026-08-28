from __future__ import annotations

import asyncio
import time

from backend.bots import BotDecision
from backend.models import Move


def create_bot_game(client, *, profile: str = "stockfish-800", color: str = "white"):
    return client.post(
        "/game/create",
        json={
            "mode": "bot",
            "bot": {"profileId": profile, "humanColor": color},
        },
    )


def test_catalog_and_validation_publish_classic_bot_options(client):
    catalog = client.get("/game/catalog")
    assert catalog.status_code == 200
    profiles = catalog.json()["botProfiles"]
    assert [profile["targetElo"] for profile in profiles] == [
        500,
        800,
        1000,
        1200,
        1500,
        2000,
        2500,
    ]
    assert all(profile["estimated"] is True for profile in profiles)

    classic = client.post("/game/validate", json={})
    assert classic.status_code == 200
    assert classic.json()["bot"] == {"eligible": True, "reason": None}

    custom = client.post(
        "/game/validate",
        json={"boardRows": 10, "boardCols": 10},
    )
    assert custom.status_code == 200
    assert custom.json()["bot"]["eligible"] is False
    assert "8x8" in custom.json()["bot"]["reason"]


def test_bot_game_persists_human_seat_and_rejects_custom_setups(client):
    created = create_bot_game(client, profile="stockfish-500", color="white")
    assert created.status_code == 200, created.text
    session = created.json()
    game = session["game"]

    assert session["role"] == "human"
    assert session["playerToken"] is None
    assert session["playerColor"] == "white"
    assert game["mode"] == "bot"
    assert game["ready"] is True
    assert game["players"] == {"white": "human", "black": "bot"}
    assert game["bot"] == {
        "profileId": "stockfish-500",
        "targetElo": 500,
        "label": "Beginner",
        "description": "Learning the basics",
        "engineId": "stockfish",
        "engineName": "Stockfish 18",
        "humanColor": "white",
        "botColor": "black",
        "status": "idle",
    }

    loaded = client.get(f"/game/{game['id']}")
    assert loaded.status_code == 200
    assert loaded.json()["bot"]["humanColor"] == "white"
    assert loaded.json()["validMoves"]

    custom = client.post(
        "/game/create",
        json={
            "mode": "bot",
            "boardRows": 10,
            "boardCols": 10,
            "bot": {"profileId": "stockfish-500", "humanColor": "white"},
        },
    )
    assert custom.status_code == 400
    assert "8x8" in custom.json()["detail"]


def test_human_and_bot_moves_share_the_rule_engine_pipeline(client, monkeypatch):
    from backend.routes.game import classic_bot_engine

    async def choose_black_reply(context):
        assert context.state.current_player == "black"
        return BotDecision(
            move=Move(fromRow=1, fromCol=4, toRow=3, toCol=4),
            engine_id="stockfish",
            engine_name="Stockfish 18",
            profile_id=context.profile_id,
            target_elo=800,
            elapsed_ms=1,
        )

    monkeypatch.setattr(classic_bot_engine, "choose_action", choose_black_reply)
    game = create_bot_game(client).json()["game"]
    moved = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 6,
            "fromCol": 4,
            "toRow": 4,
            "toCol": 4,
            "expectedVersion": game["version"],
        },
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["currentPlayer"] == "black"
    assert moved.json()["validMoves"] == []
    assert moved.json()["bot"]["status"] == "thinking"

    deadline = time.monotonic() + 2
    latest = moved.json()
    while latest["version"] < 3 and time.monotonic() < deadline:
        time.sleep(0.02)
        latest = client.get(f"/game/{game['id']}").json()

    assert latest["version"] == 3
    assert latest["currentPlayer"] == "white"
    assert latest["board"][3][4]["type"] == "pawn"
    assert [move["player"] for move in latest["history"]] == ["white", "black"]
    assert latest["validMoves"]
    assert latest["bot"]["status"] == "idle"

    restarted = client.post(
        f"/game/{game['id']}/rematch",
        json={"action": "request", "expectedVersion": latest["version"]},
    )
    assert restarted.status_code == 200
    assert restarted.json()["history"] == []
    assert restarted.json()["version"] == 4


def test_human_cannot_submit_a_move_during_the_bot_turn(client, monkeypatch):
    from backend.routes.game import classic_bot_engine

    async def delayed_reply(_context):
        await asyncio.sleep(0.15)
        return BotDecision(
            move=Move(fromRow=1, fromCol=4, toRow=3, toCol=4),
            engine_id="stockfish",
            engine_name="Stockfish 18",
            profile_id="stockfish-800",
            target_elo=800,
            elapsed_ms=1,
        )

    monkeypatch.setattr(classic_bot_engine, "choose_action", delayed_reply)
    game = create_bot_game(client).json()["game"]
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

    second_move = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 6,
            "fromCol": 3,
            "toRow": 4,
            "toCol": 3,
            "expectedVersion": moved["version"],
        },
    )
    assert second_move.status_code == 409
    assert second_move.json()["detail"] == "Wait for the bot to move."
