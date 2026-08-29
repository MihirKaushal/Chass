from __future__ import annotations

import asyncio
import time

from backend.analysis.chass import RankedAction, SearchResult
from backend.analysis.chass.action_space import legal_turn_actions
from backend.bots import BotTurnContext, ChassBotEngine
from backend.models import BotState
from backend.routes.game import game_service
from backend.rules import RuleEngine
from backend.rules.terrain import scorched_squares


def wait_for_game(client, game_id: str, predicate, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    latest = client.get(f"/game/{game_id}").json()
    while not predicate(latest) and time.monotonic() < deadline:
        time.sleep(0.03)
        latest = client.get(f"/game/{game_id}").json()
    assert predicate(latest), latest
    return latest


def simple_gambit_payload(*, draft: bool = False) -> dict:
    enabled_pieces = ["rook", "queen", "king"] if draft else ["rook", "king"]
    piece_points = {"rook": 5, "king": 0}
    piece_caps = {"rook": 1, "king": 1}
    draft_pool: dict[str, int] = {}
    if draft:
        piece_points["queen"] = 1
        piece_caps["queen"] = 1
        draft_pool = {"rook": 2, "queen": 1, "king": 2}
    return {
        "mode": "bot",
        "variant": "gambit",
        "boardRows": 8,
        "boardCols": 8,
        "configuration": {
            "schemaVersion": 2,
            "presetId": "draft_gambit" if draft else "gambit-test",
            "formationId": "custom",
            "barricadeCount": 0,
            "enabledPieces": enabled_pieces,
            "piecePoints": piece_points,
            "initialLayout": [],
            "victory": {"mode": "checkmate"},
            "customRules": {"affinityEnabled": False},
            "specialAbilities": {"enabled": False, "allowed": []},
            "gambit": {
                "enabled": True,
                "budget": 5,
                "maxPieces": 2,
                "setupRows": 2,
                "maxQueens": 1 if draft else 0,
                "pieceCaps": piece_caps,
                "draftEnabled": draft,
                "draftPool": draft_pool,
            },
        },
        "bot": {"profileId": "chass-500", "humanColor": "white"},
    }


def test_native_bot_is_the_available_fallback_and_health_is_ready(client):
    validated = client.post(
        "/game/validate",
        json={"boardRows": 10, "boardCols": 10},
    )
    assert validated.status_code == 200, validated.text
    compatibility = validated.json()["bot"]
    assert compatibility["eligible"] is True
    assert compatibility["status"] == "compatible"
    assert compatibility["engineId"] == "chass"
    assert [profile["targetElo"] for profile in compatibility["profiles"]] == [
        500,
        800,
    ]
    assert client.get("/health").json()["botEngines"]["chass"] == "ready"


def test_gambit_validation_routes_to_native_bot_before_hidden_deployment(client):
    payload = simple_gambit_payload()
    payload["mode"] = "local"
    payload.pop("bot")
    validated = client.post("/game/validate", json=payload)

    assert validated.status_code == 200, validated.text
    body = validated.json()
    assert body["valid"] is True
    assert body["bot"]["eligible"] is True
    assert body["bot"]["status"] == "compatible"
    assert body["bot"]["engineId"] == "chass"
    assert [profile["targetElo"] for profile in body["bot"]["profiles"]] == [500, 800]
    assert body["matchPredictor"]["eligible"] is False


def test_native_bot_commits_a_rule_engine_reply_in_a_custom_board_game(client):
    created = client.post(
        "/game/create",
        json={
            "mode": "bot",
            "boardRows": 10,
            "boardCols": 10,
            "bot": {"profileId": "chass-500", "humanColor": "white"},
        },
    )
    assert created.status_code == 200, created.text
    game = created.json()["game"]
    option = game["validMoves"][0]

    moved = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": option["from"]["row"],
            "fromCol": option["from"]["col"],
            "toRow": option["to"]["row"],
            "toCol": option["to"]["col"],
            "expectedVersion": game["version"],
        },
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["bot"]["status"] == "thinking"

    latest = wait_for_game(
        client,
        game["id"],
        lambda value: value["version"] >= game["version"] + 2,
    )
    assert latest["bot"]["engineId"] == "chass"
    assert latest["bot"]["status"] == "idle"
    assert latest["currentPlayer"] == "white"
    assert [record["player"] for record in latest["history"]] == ["white", "black"]


def test_native_bot_completes_private_ability_selection(client):
    baseline = client.post("/game/create", json={"mode": "local"}).json()["game"]
    configuration = baseline["configuration"]
    configuration["presetId"] = "custom"
    configuration["specialAbilities"] = {
        "enabled": True,
        "maxPerPlayer": 1,
        "allowed": ["scorch", "episcopal"],
        "parameters": configuration.get("specialAbilities", {}).get("parameters", {}),
    }
    created = client.post(
        "/game/create",
        json={
            "mode": "bot",
            "boardRows": 8,
            "boardCols": 8,
            "configuration": configuration,
            "bot": {"profileId": "chass-500", "humanColor": "white"},
        },
    )
    assert created.status_code == 200, created.text
    game = created.json()["game"]
    assert game["phase"] == "ability_selection"

    selected = client.post(
        f"/game/{game['id']}/ability",
        json={"abilityIds": ["scorch"], "expectedVersion": game["version"]},
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["bot"]["status"] == "thinking"

    latest = wait_for_game(
        client,
        game["id"],
        lambda value: value["phase"] == "play",
    )
    assert latest["abilities"]["selected"]["white"] == ["scorch"]
    assert len(latest["abilities"]["selected"]["black"]) == 1
    assert latest["abilities"]["selected"]["black"][0] in {
        "scorch",
        "episcopal",
    }


def test_native_bot_drafts_when_the_shared_pool_reaches_its_turn(client):
    created = client.post("/game/create", json=simple_gambit_payload(draft=True))
    assert created.status_code == 200, created.text
    game = created.json()["game"]
    assert game["phase"] == "draft"
    assert game["gambit"]["draftPicks"] == {
        "white": ["king"],
        "black": ["king"],
    }

    picked = client.post(
        f"/game/{game['id']}/gambit/draft",
        json={
            "action": "pick",
            "pieceType": "rook",
            "expectedVersion": game["version"],
        },
    )
    assert picked.status_code == 200, picked.text

    latest = wait_for_game(
        client,
        game["id"],
        lambda value: (
            value["version"] >= game["version"] + 2
            and value["gambit"]["draftActiveColor"] == "white"
        ),
    )
    assert latest["gambit"]["draftPicks"]["white"] == ["king", "rook"]
    assert len(latest["gambit"]["draftPicks"]["black"]) == 2


def test_native_bot_builds_and_locks_a_legal_hidden_army(client):
    created = client.post("/game/create", json=simple_gambit_payload())
    assert created.status_code == 200, created.text
    game = created.json()["game"]

    for row, col, piece_type in ((7, 4, "king"), (7, 0, "rook")):
        placed = client.post(
            f"/game/{game['id']}/gambit/deployment",
            json={
                "action": "place",
                "row": row,
                "col": col,
                "pieceType": piece_type,
                "expectedVersion": game["version"],
            },
        )
        assert placed.status_code == 200, placed.text
        game = placed.json()

    ready = client.post(
        f"/game/{game['id']}/gambit/ready",
        json={"expectedVersion": game["version"]},
    )
    assert ready.status_code == 200, ready.text
    assert ready.json()["bot"]["status"] == "thinking"

    latest = wait_for_game(
        client,
        game["id"],
        lambda value: value["phase"] == "play",
    )
    assert latest["gambit"]["deploymentReady"] == {"white": True, "black": True}
    black_types = sorted(
        piece["type"]
        for row in latest["board"]
        for piece in row
        if piece is not None and piece["color"] == "black"
    )
    assert black_types == ["king", "rook"]


def test_native_bot_can_select_and_apply_a_special_ability_action(client, monkeypatch):
    created = client.post("/game/create", json={"mode": "local"}).json()["game"]
    state = game_service.repository.get_game(created["id"]).state.clone()
    state.configuration.special_abilities.enabled = True
    state.configuration.special_abilities.allowed = ["scorch"]
    state.abilities.selected["black"] = ["scorch"]
    state.current_player = "black"
    state.bot = BotState(
        profile_id="chass-500",
        target_elo=500,
        label="Variant Explorer",
        engine_id="chass",
        human_color="white",
        bot_color="black",
    )
    rules = RuleEngine()
    rules.evaluate_state(state)
    scorch = next(
        action
        for action in legal_turn_actions(state, rules)
        if action.payload is not None and action.payload.get("actionType") == "scorch"
    )

    class ForcedSearch:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def analyze(self, _state) -> SearchResult:
            ranked = RankedAction(action=scorch, score=1.0)
            return SearchResult(
                score=1.0,
                depth=1,
                nodes=1,
                best_action=scorch,
                ranked_actions=(ranked,),
            )

    monkeypatch.setattr("backend.bots.chass.ChassSearch", ForcedSearch)
    engine = ChassBotEngine(rules)
    decision = asyncio.run(
        engine.choose_action(
            BotTurnContext(
                game_id="forced-special-action",
                game_version=1,
                state=state,
                profile_id="chass-500",
            )
        )
    )

    assert decision.action_kind == "custom"
    assert decision.payload is not None
    assert decision.payload["actionType"] == "scorch"
    next_state, _ = rules.apply_custom_action(state, "black", decision.payload)
    target = decision.payload["target"]
    assert (target["row"], target["col"]) in scorched_squares(next_state)
