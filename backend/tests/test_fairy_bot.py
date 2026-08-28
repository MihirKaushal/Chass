from __future__ import annotations

import asyncio
import time

import pytest

from backend.analysis import (
    EngineMoveSearch,
    FairyStockfishUciProvider,
    MatchAnalysisService,
    StockfishUciProvider,
    analysis_position_fen,
)
from backend.bots import (
    BotCompatibility,
    BotDecision,
    BotTurnContext,
    FairyStockfishBotEngine,
    select_bot_engine,
    verify_bot_compatibility,
)
from backend.config import PROJECT_ROOT
from backend.models import Move
from backend.models.schemas import CreateGameRequest
from backend.routes.game import game_service
from backend.rules import RuleEngine


def configuration_state(*, rows: int = 10, cols: int = 10, victory: str = "checkmate"):
    state = game_service.configuration_analysis_state(
        CreateGameRequest(
            boardRows=rows,
            boardCols=cols,
            configuration={"victory": {"mode": victory}},
        )
    )
    assert state is not None
    return state


class CompatibleFairyAnalysis:
    fairy_provider = type("Provider", (), {"public_error": None})()

    async def verify_fairy_profile(self, state, profile):
        return True, None, analysis_position_fen(state, profile)


class FakeFairyMoveProvider:
    movetime_ms = 25
    engine_name = "Fairy-Stockfish Test"

    def __init__(self, best_move: str) -> None:
        self.best_move = best_move
        self.search = None

    async def search_moves(self, fen, profile, **kwargs):
        self.search = {"fen": fen, "profile": profile, **kwargs}
        return EngineMoveSearch(
            best_move=self.best_move,
            candidates=[],
            elapsed_ms=1,
            engine_version=self.engine_name,
        )


@pytest.mark.parametrize("victory", ["checkmate", "royal_center", "check_race"])
def test_static_fairy_variants_publish_conservative_bot_profiles(victory):
    state = configuration_state(victory=victory)
    selection = select_bot_engine(state)
    assert selection.eligible is True
    assert selection.engine_id == "fairy-stockfish"

    compatibility = asyncio.run(
        verify_bot_compatibility(
            state,
            CompatibleFairyAnalysis(),
            verify=True,
        )
    )
    assert compatibility.eligible is True
    assert compatibility.status == "compatible"
    assert [profile.target_elo for profile in compatibility.profiles] == [500, 800, 1000]


def test_fairy_bot_searches_only_chass_legal_moves_and_revalidates_choice():
    state = configuration_state()
    provider = FakeFairyMoveProvider("e2e3")
    rules = RuleEngine()
    engine = FairyStockfishBotEngine(provider, rules, CompatibleFairyAnalysis())

    decision = asyncio.run(
        engine.choose_action(
            BotTurnContext(
                game_id="fairy-unit",
                game_version=1,
                state=state,
                profile_id="fairy-stockfish-800",
            )
        )
    )

    assert decision.engine_id == "fairy-stockfish"
    assert decision.target_elo == 800
    assert decision.move == Move(fromRow=8, fromCol=4, toRow=7, toCol=4)
    assert rules.validate_move(state, decision.move).is_valid
    assert provider.search is not None
    assert provider.search["limit_strength_elo"] == 800
    assert "e2e3" in provider.search["search_moves"]


def test_fairy_bot_game_persists_engine_and_uses_realtime_scheduler(client, monkeypatch):
    from backend.routes import game as game_route

    async def compatible(state, _service, *, verify):
        assert state.board.rows == 10
        assert verify is True
        return BotCompatibility(
            eligible=True,
            status="compatible",
            reason=None,
            engine_id="fairy-stockfish",
            engine_name="Fairy-Stockfish",
            profiles=select_bot_engine(state).profiles,
        )

    async def choose_black_reply(context):
        assert context.state.bot is not None
        assert context.state.bot.engine_id == "fairy-stockfish"
        return BotDecision(
            move=Move(fromRow=1, fromCol=4, toRow=2, toCol=4),
            engine_id="fairy-stockfish",
            engine_name="Fairy-Stockfish Test",
            profile_id=context.profile_id,
            target_elo=800,
            elapsed_ms=1,
        )

    monkeypatch.setattr(game_route, "verify_bot_compatibility", compatible)
    monkeypatch.setattr(game_route.fairy_bot_engine, "choose_action", choose_black_reply)

    validated = client.post(
        "/game/validate",
        json={"boardRows": 10, "boardCols": 10},
    )
    assert validated.status_code == 200, validated.text
    assert validated.json()["bot"]["engineId"] == "fairy-stockfish"
    assert [
        profile["targetElo"] for profile in validated.json()["bot"]["profiles"]
    ] == [500, 800, 1000]

    created = client.post(
        "/game/create",
        json={
            "mode": "bot",
            "boardRows": 10,
            "boardCols": 10,
            "bot": {"profileId": "fairy-stockfish-800", "humanColor": "white"},
        },
    )
    assert created.status_code == 200, created.text
    game = created.json()["game"]
    assert game["bot"]["engineId"] == "fairy-stockfish"
    assert game["bot"]["engineName"] == "Fairy-Stockfish"
    assert game["bot"]["targetElo"] == 800

    moved = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 8,
            "fromCol": 4,
            "toRow": 7,
            "toCol": 4,
            "expectedVersion": game["version"],
        },
    )
    assert moved.status_code == 200, moved.text

    deadline = time.monotonic() + 2
    latest = moved.json()
    while latest["version"] < 3 and time.monotonic() < deadline:
        time.sleep(0.02)
        latest = client.get(f"/game/{game['id']}").json()

    assert latest["version"] == 3
    assert latest["currentPlayer"] == "white"
    assert latest["board"][2][4]["type"] == "pawn"
    assert [move["player"] for move in latest["history"]] == ["white", "black"]


def test_fairy_runtime_failure_atomically_switches_to_native_bot(client, monkeypatch):
    from backend.routes import game as game_route

    async def compatible(state, _service, *, verify):
        assert state.board.rows == 10
        assert verify is True
        return BotCompatibility(
            eligible=True,
            status="compatible",
            reason=None,
            engine_id="fairy-stockfish",
            engine_name="Fairy-Stockfish",
            profiles=select_bot_engine(state).profiles,
        )

    async def parity_failure(_context):
        raise RuntimeError("Fairy legal-move parity failed for this position.")

    async def native_reply(context):
        assert context.profile_id == "chass-800"
        return BotDecision(
            move=Move(fromRow=1, fromCol=4, toRow=2, toCol=4),
            engine_id="chass",
            engine_name="Chass Engine",
            profile_id="chass-800",
            target_elo=800,
            elapsed_ms=1,
        )

    monkeypatch.setattr(game_route, "verify_bot_compatibility", compatible)
    monkeypatch.setattr(game_route.fairy_bot_engine, "choose_action", parity_failure)
    monkeypatch.setattr(game_route.chass_bot_engine, "choose_action", native_reply)

    created = client.post(
        "/game/create",
        json={
            "mode": "bot",
            "boardRows": 10,
            "boardCols": 10,
            "bot": {"profileId": "fairy-stockfish-1000", "humanColor": "white"},
        },
    )
    assert created.status_code == 200, created.text
    game = created.json()["game"]

    moved = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 8,
            "fromCol": 4,
            "toRow": 7,
            "toCol": 4,
            "expectedVersion": game["version"],
        },
    )
    assert moved.status_code == 200, moved.text

    deadline = time.monotonic() + 2
    latest = moved.json()
    while latest["version"] < 3 and time.monotonic() < deadline:
        time.sleep(0.02)
        latest = client.get(f"/game/{game['id']}").json()

    assert latest["version"] == 3
    assert latest["bot"]["engineId"] == "chass"
    assert latest["bot"]["profileId"] == "chass-800"
    assert latest["bot"]["targetElo"] == 800
    assert latest["board"][2][4]["type"] == "pawn"
    assert latest["lastMoveExplanation"].startswith(
        "Chass Engine safely took over after Fairy-Stockfish became unavailable."
    )


FAIRY_BINARY = PROJECT_ROOT / ".stockfish" / "fairy-stockfish"


@pytest.mark.skipif(not FAIRY_BINARY.is_file(), reason="Fairy-Stockfish is not installed")
def test_real_fairy_bot_returns_a_rule_engine_legal_move():
    state = configuration_state()
    rules = RuleEngine()
    fairy = FairyStockfishUciProvider(
        configured_path=str(FAIRY_BINARY),
        enabled=True,
        movetime_ms=40,
        hash_mb=4,
        threads=1,
        startup_timeout_seconds=10,
        startup_attempts=1,
    )
    stockfish = StockfishUciProvider(configured_path="", enabled=False)
    analysis = MatchAnalysisService(stockfish, rules, fairy_provider=fairy)
    engine = FairyStockfishBotEngine(fairy, rules, analysis)

    async def scenario():
        try:
            decision = await engine.choose_action(
                BotTurnContext(
                    game_id="fairy-real",
                    game_version=1,
                    state=state,
                    profile_id="fairy-stockfish-500",
                )
            )
            assert decision.engine_id == "fairy-stockfish"
            assert rules.validate_move(state, decision.move).is_valid
        finally:
            await analysis.shutdown()

    asyncio.run(scenario())
