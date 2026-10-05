from __future__ import annotations

import asyncio
import time

import pytest

from backend.bots import (
    BotDecision,
    BotTurnContext,
    timed_stockfish_response_delay_seconds,
)
from backend.catalog import classic_layout
from backend.models import Move


def create_bot_game(client, *, profile: str = "stockfish-800", color: str = "white"):
    return client.post(
        "/game/create",
        json={
            "mode": "bot",
            "bot": {"profileId": profile, "humanColor": color},
        },
    )


def timed_bot_payload(*, profile: str = "stockfish-800") -> dict:
    return {
        "mode": "bot",
        "bot": {"profileId": profile, "humanColor": "white"},
        "configuration": {
            "schemaVersion": 2,
            "presetId": "classic",
            "formationId": "classic",
            "initialLayout": classic_layout(8, 8),
            "victory": {"mode": "timed", "timeSeconds": 60},
        },
    }


def test_catalog_and_validation_publish_classic_bot_options(client):
    catalog = client.get("/game/catalog")
    assert catalog.status_code == 200
    profiles = catalog.json()["botProfiles"]
    stockfish_profiles = [
        profile for profile in profiles if profile["engineId"] == "stockfish"
    ]
    fairy_profiles = [
        profile for profile in profiles if profile["engineId"] == "fairy-stockfish"
    ]
    chass_profiles = [
        profile for profile in profiles if profile["engineId"] == "chass"
    ]
    assert [profile["targetElo"] for profile in stockfish_profiles] == [
        500,
        800,
        1000,
        1200,
        1500,
        2000,
        2500,
    ]
    assert [profile["targetElo"] for profile in fairy_profiles] == [500, 800, 1000]
    assert [profile["targetElo"] for profile in chass_profiles] == [500, 800]
    assert all(profile["estimated"] is True for profile in profiles)

    classic = client.post("/game/validate", json={})
    assert classic.status_code == 200
    classic_bot = classic.json()["bot"]
    assert classic_bot["eligible"] is True
    assert classic_bot["status"] == "compatible"
    assert classic_bot["engineId"] == "stockfish"
    assert [profile["targetElo"] for profile in classic_bot["profiles"]] == [
        500,
        800,
        1000,
        1200,
        1500,
        2000,
        2500,
    ]

    custom = client.post(
        "/game/validate",
        json={"boardRows": 10, "boardCols": 10},
    )
    assert custom.status_code == 200
    assert custom.json()["bot"]["eligible"] is True
    assert custom.json()["bot"]["engineId"] == "chass"
    assert custom.json()["bot"]["status"] == "compatible"
    assert [
        profile["targetElo"] for profile in custom.json()["bot"]["profiles"]
    ] == [500, 800]


def test_timed_classic_games_stay_on_stockfish(client):
    payload = timed_bot_payload()
    validation_payload = {**payload, "mode": "local", "bot": None}
    validation = client.post("/game/validate", json=validation_payload)
    assert validation.status_code == 200, validation.text
    assert validation.json()["bot"]["engineId"] == "stockfish"

    created = client.post("/game/create", json=payload)
    assert created.status_code == 200, created.text
    game = created.json()["game"]
    assert game["bot"]["engineId"] == "stockfish"
    assert game["clock"]["initialSeconds"] == 60


def test_timed_stockfish_pacing_is_elo_and_clock_pressure_aware(client):
    from backend.routes.game import game_service

    created = client.post(
        "/game/create",
        json=timed_bot_payload(profile="stockfish-500"),
    ).json()["game"]
    record = game_service.repository.get_game(created["id"])
    assert record is not None and record.state.clock is not None

    beginner = BotTurnContext(
        game_id=record.state.id,
        game_version=record.version,
        state=record.state.clone(),
        profile_id="stockfish-500",
    )
    master = BotTurnContext(
        game_id=record.state.id,
        game_version=record.version,
        state=record.state.clone(),
        profile_id="stockfish-2500",
    )
    beginner_delay = timed_stockfish_response_delay_seconds(beginner, 50)
    master_delay = timed_stockfish_response_delay_seconds(master, 50)
    assert beginner_delay > master_delay >= 0

    pressured_state = record.state.clone()
    assert pressured_state.bot is not None and pressured_state.clock is not None
    pressured_state.clock.remaining_seconds[pressured_state.bot.bot_color] = 3
    pressured = BotTurnContext(
        game_id=record.state.id,
        game_version=record.version,
        state=pressured_state,
        profile_id="stockfish-500",
    )
    assert (
        timed_stockfish_response_delay_seconds(pressured, 50)
        < beginner_delay
    )


def test_bot_game_persists_human_seat_and_routes_custom_setups(client):
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

    changed_rules = client.post(
        f"/game/{game['id']}/rules",
        json={
            "expectedVersion": game["version"],
            "rules": [{"id": "double_capture_rook", "enabled": True}],
        },
    )
    assert changed_rules.status_code == 409
    assert changed_rules.json()["detail"] == (
        "Bot game settings are fixed after the match is created."
    )

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
    assert custom.json()["detail"] == (
        "Choose a Chass Engine difficulty for this configuration."
    )

    custom_bot = client.post(
        "/game/create",
        json={
            "mode": "bot",
            "boardRows": 10,
            "boardCols": 10,
            "bot": {"profileId": "chass-500", "humanColor": "white"},
        },
    )
    assert custom_bot.status_code == 200, custom_bot.text
    assert custom_bot.json()["game"]["bot"]["engineId"] == "chass"

    canonical_ui_payload = {
        "mode": "bot",
        "boardRows": 8,
        "boardCols": 8,
        "bot": {"profileId": "stockfish-500", "humanColor": "white"},
        "configuration": {
            "schemaVersion": 2,
            "presetId": "classic",
            "formationId": "classic",
            "enabledPieces": ["pawn", "knight", "bishop", "rook", "queen", "king"],
            "piecePoints": {
                "pawn": 1,
                "knight": 3,
                "bishop": 3,
                "rook": 5,
                "queen": 9,
                "king": 0,
            },
            "initialLayout": game["configuration"]["initialLayout"],
            "victory": {"mode": "checkmate", "kingPoints": 0},
            "customRules": {"affinityEnabled": False},
            "specialAbilities": {"enabled": False, "allowed": []},
            "gambit": {"enabled": False},
        },
    }
    canonical = client.post("/game/create", json=canonical_ui_payload)
    assert canonical.status_code == 200, canonical.text


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


@pytest.mark.parametrize("timed", [False, True])
def test_bot_turn_reaches_the_human_over_the_existing_websocket(
    client,
    monkeypatch,
    timed,
):
    from backend.routes import game as game_routes

    async def choose_black_reply(context):
        return BotDecision(
            move=Move(fromRow=1, fromCol=3, toRow=3, toCol=3),
            engine_id="stockfish",
            engine_name="Stockfish 18",
            profile_id=context.profile_id,
            target_elo=800,
            elapsed_ms=1,
        )

    monkeypatch.setattr(
        game_routes.classic_bot_engine,
        "choose_action",
        choose_black_reply,
    )
    monkeypatch.setattr(
        game_routes,
        "timed_stockfish_response_delay_seconds",
        lambda *_args: 0.0,
    )
    created = (
        client.post("/game/create", json=timed_bot_payload())
        if timed
        else create_bot_game(client)
    )
    game = created.json()["game"]

    with client.websocket_connect(f"/game/ws/{game['id']}") as websocket:
        websocket.send_json({"type": "authenticate", "token": None})
        initial = websocket.receive_json()
        assert initial["type"] == "game_state"
        assert initial["game"]["bot"]["humanColor"] == "white"
        assert bool(initial["game"].get("clock")) is timed
        if timed:
            assert isinstance(initial["game"]["clock"]["turnStartedAt"], str)
        assert websocket.receive_json()["type"] == "presence"

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
        assert moved.status_code == 200

        event_types: list[str] = []
        final = None
        for _ in range(5):
            event = websocket.receive_json()
            event_types.append(event["type"])
            if event.get("game", {}).get("version") == 3:
                final = event["game"]
                break

        assert "bot_thinking" in event_types
        assert final is not None
        assert final["currentPlayer"] == "white"
        assert final["board"][3][3]["type"] == "pawn"
        if timed:
            assert final["clock"]["activeColor"] == "white"
            assert isinstance(final["clock"]["turnStartedAt"], str)
