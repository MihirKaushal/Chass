from __future__ import annotations

import asyncio

import pytest

from backend.analysis.classic import (
    classic_analysis_eligibility,
    classic_position_fen,
    extract_position_factors,
    synchronize_match_predictor_setting,
)
from backend.analysis.service import MatchAnalysisService
from backend.analysis.stockfish import EngineAnalysis, parse_uci_info
from backend.catalog import classic_layout
from backend.routes.game import game_service
from backend.rules import RuleEngine


class FakeStockfishProvider:
    enabled = True
    ready = True
    last_error = None
    engine_name = "Stockfish Test"

    def __init__(self) -> None:
        self.calls = 0

    async def start(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def analyze(self, fen: str) -> EngineAnalysis:
        self.calls += 1
        await asyncio.sleep(0)
        assert " w " in fen
        return EngineAnalysis(
            centipawns=34,
            mate_in=None,
            win=410,
            draw=400,
            loss=190,
            depth=15,
            nodes=12_345,
            principal_variation=["e2e4", "e7e5"],
            elapsed_ms=37,
            engine_version=self.engine_name,
        )


class FailingStockfishProvider(FakeStockfishProvider):
    async def analyze(self, fen: str) -> EngineAnalysis:
        self.calls += 1
        raise RuntimeError("engine test failure")


def create_default_game(client) -> dict:
    response = client.post("/game/create", json={"mode": "local"})
    assert response.status_code == 200, response.text
    return response.json()["game"]


def classic_request(*, predictor_enabled: bool = True, queen_points: int = 9) -> dict:
    return {
        "mode": "local",
        "boardRows": 8,
        "boardCols": 8,
        "configuration": {
            "presetId": "classic",
            "formationId": "classic",
            "matchPredictorEnabled": predictor_enabled,
            "enabledPieces": ["pawn", "knight", "bishop", "rook", "queen", "king"],
            "piecePoints": {
                "pawn": 1,
                "knight": 3,
                "bishop": 3,
                "rook": 5,
                "queen": queen_points,
                "king": 0,
            },
            "initialLayout": classic_layout(8, 8),
            "victory": {"mode": "checkmate"},
            "customRules": {"affinityEnabled": False},
            "specialAbilities": {"enabled": False, "allowed": []},
            "gambit": {"enabled": False},
        },
    }


def test_untouched_classic_game_enables_match_predictor(client):
    game = create_default_game(client)

    assert game["configuration"]["matchPredictorEnabled"] is True
    analysis = client.get(f"/game/{game['id']}/analysis")
    assert analysis.status_code == 200
    assert analysis.json()["enabled"] is True
    assert analysis.json()["eligible"] is True
    assert analysis.json()["status"] == "unavailable"


def test_backend_overrides_incompatible_predictor_request(client):
    custom_values = client.post(
        "/game/create",
        json=classic_request(queen_points=10),
    )
    assert custom_values.status_code == 200, custom_values.text
    assert custom_values.json()["game"]["configuration"]["matchPredictorEnabled"] is False

    custom_size = client.post(
        "/game/create",
        json={"mode": "local", "boardRows": 10, "boardCols": 10},
    )
    assert custom_size.status_code == 200, custom_size.text
    assert custom_size.json()["game"]["configuration"]["matchPredictorEnabled"] is False


@pytest.mark.parametrize(
    ("mutation", "reason_fragment"),
    [
        (lambda state: setattr(state.board, "rows", 10), "8x8"),
        (
            lambda state: setattr(state.piece_definitions["queen"], "points", 10),
            "definitions or values",
        ),
        (
            lambda state: setattr(state.configuration.custom_rules, "affinity_enabled", True),
            "Custom rules",
        ),
        (
            lambda state: setattr(state.configuration.special_abilities, "enabled", True),
            "Special abilities",
        ),
        (
            lambda state: state.configuration.initial_layout.__setitem__(
                0,
                {**state.configuration.initial_layout[0], "col": 2},
            ),
            "starting position",
        ),
    ],
)
def test_any_classic_customization_disables_predictor(
    client,
    mutation,
    reason_fragment: str,
):
    game = create_default_game(client)
    state = game_service.repository.get_game(game["id"]).state
    mutation(state)

    eligibility = classic_analysis_eligibility(state)
    assert eligibility.eligible is False
    assert reason_fragment in (eligibility.reason or "")

    synchronize_match_predictor_setting(state)
    assert state.configuration.match_predictor_enabled is False


def test_player_can_explicitly_disable_predictor(client):
    created = client.post(
        "/game/create",
        json=classic_request(predictor_enabled=False),
    )
    assert created.status_code == 200, created.text
    game = created.json()["game"]
    assert game["configuration"]["matchPredictorEnabled"] is False

    response = client.get(f"/game/{game['id']}/analysis")
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert response.json()["enabled"] is False


def test_classic_fen_tracks_turn_castling_and_en_passant(client):
    game = create_default_game(client)
    state = game_service.repository.get_game(game["id"]).state
    assert classic_position_fen(state) == (
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    )

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
    state = game_service.repository.get_game(game["id"]).state
    assert classic_position_fen(state) == (
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    )


def test_position_factors_explain_material_and_initial_balance(client):
    game = create_default_game(client)
    state = game_service.repository.get_game(game["id"]).state
    factors = {factor.id: factor for factor in extract_position_factors(state, RuleEngine())}

    assert set(factors) == {
        "material",
        "king_safety",
        "piece_activity",
        "pawn_structure",
        "center_control",
    }
    assert factors["material"].whiteValue == 39
    assert factors["material"].blackValue == 39
    assert factors["material"].advantage == "balanced"

    state.board.grid[1][0] = None
    factors = {factor.id: factor for factor in extract_position_factors(state, RuleEngine())}
    assert factors["material"].blackValue == 38
    assert factors["material"].advantage == "white"


def test_uci_parser_handles_probabilities_and_mate_scores():
    parsed = parse_uci_info(
        "info depth 17 nodes 2048 score cp 42 wdl 450 380 170 pv e2e4 e7e5"
    )
    assert parsed == {
        "depth": 17,
        "nodes": 2048,
        "centipawns": 42,
        "mate_in": None,
        "win": 450,
        "draw": 380,
        "loss": 170,
        "principal_variation": ["e2e4", "e7e5"],
    }

    mate = parse_uci_info("info depth 20 score mate -3 pv h5h2")
    assert mate["centipawns"] is None
    assert mate["mate_in"] == -3


def test_analysis_service_caches_engine_results_and_publishes(client):
    game = create_default_game(client)
    state = game_service.repository.get_game(game["id"]).state
    provider = FakeStockfishProvider()
    service = MatchAnalysisService(provider, RuleEngine())
    published = []

    async def collect(result):
        published.append(result)

    service.set_listener(collect)

    async def scenario():
        pending = await service.request(state, game["version"])
        assert pending.status == "analyzing"
        await service.wait_for_game(state.id)

        ready = await service.request(state, game["version"])
        assert ready.status == "ready"
        assert ready.evaluation.centipawns == 34
        assert ready.outcome.whiteWin == pytest.approx(0.41)
        assert ready.outcome.draw == pytest.approx(0.40)
        assert ready.outcome.blackWin == pytest.approx(0.19)
        assert ready.principalVariation == ["e2e4", "e7e5"]

        cached = await service.request(state, game["version"])
        assert cached.status == "ready"
        assert provider.calls == 1
        assert len(published) == 1
        await service.shutdown()

    asyncio.run(scenario())


def test_analysis_failure_stops_rest_polling_retry_loop(client):
    game = create_default_game(client)
    state = game_service.repository.get_game(game["id"]).state
    provider = FailingStockfishProvider()
    service = MatchAnalysisService(provider, RuleEngine())

    async def scenario():
        pending = await service.request(state, game["version"])
        assert pending.status == "analyzing"
        await service.wait_for_game(state.id)

        unavailable = await service.request(state, game["version"])
        assert unavailable.status == "unavailable"
        repeated = await service.request(state, game["version"])
        assert repeated.status == "unavailable"
        assert provider.calls == 1
        await service.shutdown()

    asyncio.run(scenario())
