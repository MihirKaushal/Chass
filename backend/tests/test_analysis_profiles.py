from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.analysis.chass import ChassAnalysisProvider
from backend.analysis.classic import extract_position_factors
from backend.analysis.fairy import (
    FairyPositionInspection,
    FairyStockfishUciProvider,
    parse_fairy_perft_move,
)
from backend.analysis.profiles import (
    FAIRY_MAX_FILES,
    FAIRY_MAX_RANKS,
    analysis_position_fen,
    analysis_position_hash,
    select_analysis_profile,
)
from backend.analysis.service import MatchAnalysisService
from backend.analysis.stockfish import EngineAnalysis
from backend.models import Move
from backend.routes.game import game_service
from backend.rules import RuleEngine


class IdleStockfishProvider:
    enabled = True
    ready = True
    last_error = None
    public_error = None
    engine_name = "Stockfish Test"

    async def start(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def analyze(self, fen: str) -> EngineAnalysis:  # pragma: no cover - route guard
        raise AssertionError("Stockfish must not analyze a Fairy profile")


class FakeFairyProvider:
    enabled = True
    ready = True
    last_error = None
    public_error = None
    engine_name = "Fairy-Stockfish Test"

    def __init__(
        self,
        legal_moves: frozenset[tuple[int, int, int, int]],
        terminal_outcome: str | None = None,
    ) -> None:
        self.legal_moves = legal_moves
        self.terminal_outcome = terminal_outcome
        self.inspection_calls = 0
        self.analysis_calls = 0

    async def close(self) -> None:
        return None

    async def inspect_position(self, fen, profile, **kwargs) -> FairyPositionInspection:
        self.inspection_calls += 1
        assert profile.variant_name and profile.variant_definition
        assert "[chass_" in profile.variant_definition
        return FairyPositionInspection(self.legal_moves, self.terminal_outcome)

    async def analyze(self, fen, profile) -> EngineAnalysis:
        self.analysis_calls += 1
        assert profile.engine_id == "fairy-stockfish"
        return EngineAnalysis(
            centipawns=28,
            mate_in=None,
            win=390,
            draw=430,
            loss=180,
            depth=10,
            nodes=1_000,
            engine_version=self.engine_name,
        )


def create_state(client, *, rows: int = 8, cols: int = 8):
    response = client.post(
        "/game/create",
        json={"mode": "local", "boardRows": rows, "boardCols": cols},
    )
    assert response.status_code == 200, response.text
    game_id = response.json()["game"]["id"]
    return game_service.repository.get_game(game_id).state


def test_stockfish_is_preferred_before_deterministic_fairy_profiles(client):
    classic = create_state(client)
    classic_selection = select_analysis_profile(classic)
    assert classic_selection.profile is not None
    assert classic_selection.profile.engine_id == "stockfish"

    large = create_state(client, rows=10, cols=10)
    first = select_analysis_profile(large)
    second = select_analysis_profile(large.clone())
    assert first.profile is not None
    assert second.profile is not None
    assert first.profile.engine_id == "fairy-stockfish"
    assert first.profile.profile_id == second.profile.profile_id
    assert first.profile.variant_definition == second.profile.variant_definition
    assert "promotionRegionWhite = *10" in (first.profile.variant_definition or "")
    assert "promotionRegionBlack = *1" in (first.profile.variant_definition or "")
    assert "doubleStepRegionWhite = *2" in (first.profile.variant_definition or "")
    assert "doubleStepRegionBlack = *9" in (first.profile.variant_definition or "")

    point_labels = large.clone()
    point_labels.piece_definitions["queen"].points = 17
    point_profile = select_analysis_profile(point_labels).profile
    assert point_profile is not None
    assert point_profile.profile_id == first.profile.profile_id

    check_race = large.clone()
    check_race.configuration.victory.mode = "check_race"
    check_race.configuration.victory.check_target = 4
    check_profile = select_analysis_profile(check_race).profile
    assert check_profile is not None
    assert check_profile.profile_id != first.profile.profile_id
    assert "checkCounting = true" in (check_profile.variant_definition or "")


def test_configuration_validation_reports_the_auto_selected_engine(client):
    classic = client.post(
        "/game/validate",
        json={"mode": "local", "boardRows": 8, "boardCols": 8},
    )
    assert classic.status_code == 200, classic.text
    classic_profile = classic.json()["matchPredictor"]
    assert classic_profile["status"] == "compatible"
    assert classic_profile["engineId"] == "stockfish"
    assert classic_profile["engineName"] == "Stockfish 18"

    large = client.post(
        "/game/validate",
        json={"mode": "local", "boardRows": 10, "boardCols": 10},
    )
    assert large.status_code == 200, large.text
    large_profile = large.json()["matchPredictor"]
    assert large_profile["eligible"] is True
    assert large_profile["engineId"] == "fairy-stockfish"
    assert large_profile["engineName"] == "Fairy-Stockfish"
    assert large_profile["status"] in {"compatible", "unavailable"}


def test_fairy_limits_and_stateful_features_fall_back_to_chass(client):
    maximum = create_state(client, rows=FAIRY_MAX_RANKS, cols=FAIRY_MAX_FILES)
    assert select_analysis_profile(maximum).eligible is True

    too_tall = maximum.clone()
    too_tall.board.rows = FAIRY_MAX_RANKS + 1
    result = select_analysis_profile(too_tall, require_enabled=False)
    assert result.eligible is True
    assert result.profile is not None
    assert result.profile.engine_id == "chass"

    too_wide = maximum.clone()
    too_wide.board.cols = FAIRY_MAX_FILES + 1
    result = select_analysis_profile(too_wide, require_enabled=False)
    assert result.eligible is True
    assert result.profile is not None
    assert result.profile.engine_id == "chass"

    affinity = maximum.clone()
    affinity.configuration.custom_rules.affinity_enabled = True
    result = select_analysis_profile(affinity, require_enabled=False)
    assert result.eligible is True
    assert result.profile is not None
    assert result.profile.engine_id == "chass"

    custom_movement = maximum.clone()
    custom_movement.piece_definitions["rook"].patterns[0].repeat = False
    result = select_analysis_profile(custom_movement, require_enabled=False)
    assert result.eligible is True
    assert result.profile is not None
    assert result.profile.engine_id == "chass"

    missing_promotion = maximum.clone()
    missing_promotion.configuration.enabled_piece_types.remove("queen")
    missing_promotion.piece_definitions.pop("queen")
    for row, board_row in enumerate(missing_promotion.board.grid):
        for col, piece in enumerate(board_row):
            if piece is not None and piece.type == "queen":
                missing_promotion.board.grid[row][col] = None
    result = select_analysis_profile(missing_promotion, require_enabled=False)
    assert result.eligible is True
    assert result.profile is not None
    assert result.profile.engine_id == "chass"


def test_generated_fairy_fen_and_perft_parser_support_largeboard_coordinates(client):
    state = create_state(client, rows=10, cols=12)
    profile = select_analysis_profile(state).profile
    assert profile is not None
    fen = analysis_position_fen(state, profile)

    assert len(fen.split()[0].split("/")) == 10
    assert parse_fairy_perft_move("a10b8: 1", rows=10, cols=12) == (0, 0, 2, 1)
    assert parse_fairy_perft_move("l2l1q: 1", rows=10, cols=12) == (8, 11, 9, 11)
    assert parse_fairy_perft_move("m2m3: 1", rows=10, cols=12) is None


def test_fairy_compatibility_requires_chass_move_parity(client):
    state = create_state(client, rows=10, cols=10)
    engine = RuleEngine()
    expected_moves = MatchAnalysisService._chass_move_keys(state, engine)
    fairy = FakeFairyProvider(expected_moves)
    service = MatchAnalysisService(
        IdleStockfishProvider(),
        engine,
        fairy_provider=fairy,
    )

    async def matching_scenario():
        compatibility = await service.configuration_compatibility(state, verify=True)
        assert compatibility.status == "compatible"
        assert compatibility.engineId == "fairy-stockfish"
        assert compatibility.parityChecked is True

        pending = await service.request(state, version=1)
        assert pending.status == "analyzing"
        assert pending.engineId == "fairy-stockfish"
        await service.wait_for_game(state.id)
        ready = await service.request(state, version=1)
        assert ready.status == "ready"
        assert ready.engineName == "Fairy-Stockfish"
        assert ready.calibrated is False
        assert fairy.inspection_calls == 1
        assert fairy.analysis_calls == 1
        await service.shutdown()

    asyncio.run(matching_scenario())

    mismatch_service = MatchAnalysisService(
        IdleStockfishProvider(),
        engine,
        fairy_provider=FakeFairyProvider(frozenset()),
        chass_provider=ChassAnalysisProvider(engine, movetime_ms=40),
    )

    async def mismatch_scenario():
        compatibility = await mismatch_service.configuration_compatibility(
            state,
            verify=True,
        )
        assert compatibility.status == "compatible"
        assert compatibility.engineId == "chass"
        assert compatibility.parityChecked is False
        assert "legal-move parity failed" in (compatibility.reason or "")
        pending = await mismatch_service.request(state, version=1)
        assert pending.status == "analyzing"
        await mismatch_service.wait_for_game(state.id)
        ready = await mismatch_service.request(state, version=1)
        assert ready.status == "ready"
        assert ready.engineId == "chass"
        assert "analyzing this position instead" in (ready.reason or "")
        await mismatch_service.shutdown()

    asyncio.run(mismatch_scenario())


def test_fairy_terminal_outcome_must_match_chass(client):
    state = create_state(client, rows=10, cols=10)
    profile = select_analysis_profile(state).profile
    assert profile is not None
    state.winner = "white"
    state.game_status = "checkmate"
    state.phase = "finished"
    fen = analysis_position_fen(state, profile)
    position_hash = analysis_position_hash(state, profile, fen)

    async def scenario():
        matching = MatchAnalysisService(
            IdleStockfishProvider(),
            RuleEngine(),
            fairy_provider=FakeFairyProvider(frozenset(), "white"),
        )
        assert await matching._verify_fairy_parity(
            state,
            profile,
            fen,
            position_hash,
        ) == (True, None)
        await matching.shutdown()

        mismatching = MatchAnalysisService(
            IdleStockfishProvider(),
            RuleEngine(),
            fairy_provider=FakeFairyProvider(frozenset(), "black"),
        )
        compatible, reason = await mismatching._verify_fairy_parity(
            state,
            profile,
            fen,
            position_hash,
        )
        assert compatible is False
        assert "terminal-outcome parity failed" in (reason or "")
        await mismatching.shutdown()

    asyncio.run(scenario())


def test_position_factors_use_adaptive_board_bounds_and_center(client):
    state = create_state(client, rows=10, cols=10)

    class AdaptiveFactorEngine:
        @staticmethod
        def find_king(candidate, color):
            for row, board_row in enumerate(candidate.board.grid):
                for col, piece in enumerate(board_row):
                    if piece is not None and piece.type == "king" and piece.color == color:
                        return row, col
            return None

        @staticmethod
        def generate_piece_attacks(candidate, row, col):
            piece = candidate.board.grid[row][col]
            return {(5, 5)} if piece is not None and piece.color == "white" else set()

        @staticmethod
        def get_valid_moves_for_color(candidate, color):
            return []

    factors = {
        factor.id: factor for factor in extract_position_factors(state, AdaptiveFactorEngine())
    }
    assert factors["king_safety"].whiteValue is not None
    assert factors["center_control"].whiteValue == 1
    assert factors["center_control"].blackValue == 0


def test_raw_fairy_variant_definitions_are_rejected(client):
    response = client.post(
        "/game/create",
        json={
            "mode": "local",
            "configuration": {
                "fairyVariantIni": "[unsafe:chess]\\nmaxRank = 16",
            },
        },
    )
    assert response.status_code == 422
    assert "Raw Fairy-Stockfish profiles are not accepted" in response.text


FAIRY_BINARY = Path(__file__).parents[2] / ".stockfish" / "fairy-stockfish"


@pytest.mark.skipif(not FAIRY_BINARY.is_file(), reason="Fairy-Stockfish is not installed")
def test_real_fairy_engine_matches_legal_moves_and_terminal_variants(client):
    active = create_state(client, rows=10, cols=10)
    active_profile = select_analysis_profile(active).profile
    assert active_profile is not None

    provider = FairyStockfishUciProvider(
        configured_path=str(FAIRY_BINARY),
        enabled=True,
        movetime_ms=25,
        hash_mb=4,
        threads=1,
        startup_timeout_seconds=10,
        startup_attempts=1,
    )

    def remembered_pieces(state):
        pieces = {}
        for row in state.board.grid:
            for piece in row:
                if piece is not None:
                    pieces.setdefault((piece.color, piece.type), piece.model_copy(deep=True))
        return pieces

    async def scenario():
        try:
            engine = RuleEngine()

            async def assert_move_parity(candidate):
                candidate_profile = select_analysis_profile(candidate).profile
                assert candidate_profile is not None
                candidate_fen = analysis_position_fen(candidate, candidate_profile)
                inspection = await provider.inspect_position(
                    candidate_fen,
                    candidate_profile,
                    rows=candidate.board.rows,
                    cols=candidate.board.cols,
                    side_to_move=candidate.current_player,
                )
                expected = MatchAnalysisService._chass_move_keys(candidate, engine)
                assert inspection.legal_moves == expected
                return candidate_fen, candidate_profile

            active_fen, active_profile = await assert_move_parity(active)
            estimate = await provider.analyze(active_fen, active_profile)
            assert estimate.centipawns is not None or estimate.mate_in is not None

            after_white, _ = engine.apply_move(
                active,
                Move(fromRow=8, fromCol=1, toRow=7, toCol=1),
            )
            await assert_move_parity(after_white)
            assert (1, 1, 3, 1) in MatchAnalysisService._chass_move_keys(
                after_white,
                engine,
            )

            after_black, _ = engine.apply_move(
                after_white,
                Move(fromRow=1, fromCol=1, toRow=3, toCol=1),
            )
            await assert_move_parity(after_black)

            checkmate = active.clone()
            checkmate_profile = select_analysis_profile(checkmate).profile
            assert checkmate_profile is not None
            pieces = remembered_pieces(checkmate)
            checkmate.board.grid = [[None for _ in range(10)] for _ in range(10)]
            checkmate.board.grid[0][0] = pieces[("black", "king")]
            checkmate.board.grid[1][1] = pieces[("white", "queen")]
            checkmate.board.grid[2][2] = pieces[("white", "king")]
            checkmate.current_player = "black"
            RuleEngine().evaluate_state(checkmate)
            checkmate_inspection = await provider.inspect_position(
                analysis_position_fen(checkmate, checkmate_profile),
                checkmate_profile,
                rows=10,
                cols=10,
                side_to_move="black",
                probe_terminal=True,
            )
            assert checkmate.game_status == "checkmate"
            assert checkmate_inspection.terminal_outcome == "white"

            royal_center = active.clone()
            royal_center.configuration.victory.mode = "royal_center"
            royal_profile = select_analysis_profile(royal_center).profile
            assert royal_profile is not None
            pieces = remembered_pieces(royal_center)
            royal_center.board.grid = [[None for _ in range(10)] for _ in range(10)]
            royal_center.board.grid[0][0] = pieces[("black", "king")]
            royal_center.board.grid[4][4] = pieces[("white", "king")]
            royal_center.current_player = "black"
            RuleEngine().evaluate_state(royal_center)
            royal_inspection = await provider.inspect_position(
                analysis_position_fen(royal_center, royal_profile),
                royal_profile,
                rows=10,
                cols=10,
                side_to_move="black",
                probe_terminal=True,
            )
            assert royal_center.game_status == "royal_center"
            assert royal_inspection.terminal_outcome == "white"

            check_race = active.clone()
            check_race.configuration.victory.mode = "check_race"
            check_race.configuration.victory.check_target = 3
            race_profile = select_analysis_profile(check_race).profile
            assert race_profile is not None
            check_race.check_race.checks["white"] = 3
            check_race.current_player = "black"
            RuleEngine().evaluate_state(check_race)
            race_inspection = await provider.inspect_position(
                analysis_position_fen(check_race, race_profile),
                race_profile,
                rows=10,
                cols=10,
                side_to_move="black",
                probe_terminal=True,
            )
            assert check_race.game_status == "check_race"
            assert race_inspection.terminal_outcome == "white"
        finally:
            await provider.close()

    asyncio.run(scenario())
