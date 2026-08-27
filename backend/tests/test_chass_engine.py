from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone

import pytest

from backend.analysis.chass import (
    ChassAnalysisProvider,
    ChassEvaluator,
    chass_position_hash,
)
from backend.analysis.chass.action_space import legal_turn_actions
from backend.analysis.chass.evaluator import intrinsic_piece_value
from backend.analysis.chass.search import ChassSearch
from backend.analysis.chass.weights import (
    ABILITY_PARAMETER_COVERAGE,
    MODEL_VERSION,
    PIECE_PARAMETER_COVERAGE,
    RULE_EVALUATION_COVERAGE,
    VICTORY_MODE_COVERAGE,
)
from backend.analysis.profiles import select_analysis_profile
from backend.analysis.service import MatchAnalysisService
from backend.catalog import (
    SPECIAL_ABILITIES,
    VICTORY_MODES,
    build_catalog_piece_definitions,
)
from backend.models import ClassicRuleState, ClockState, Move, Piece
from backend.routes.game import game_service
from backend.rules import RuleEngine


class IdleStockfishProvider:
    enabled = True
    ready = True
    last_error = None
    public_error = None
    engine_name = "Stockfish Test"

    def __init__(self) -> None:
        self.calls = 0

    async def start(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def analyze(self, fen: str):  # pragma: no cover - routing guard
        self.calls += 1
        raise AssertionError(f"Stockfish must not receive a Chass position: {fen}")


def _default_state(client):
    response = client.post("/game/create", json={"mode": "local"})
    assert response.status_code == 200, response.text
    game_id = response.json()["game"]["id"]
    return game_service.repository.get_game(game_id).state.clone()


def _piece(state, piece_type: str, color: str, *, points: int | None = None) -> Piece:
    definition = state.piece_definitions[piece_type]
    return Piece(
        type=piece_type,
        name=definition.display_name,
        color=color,
        points=definition.points if points is None else points,
        is_custom=definition.is_custom,
        custom_attributes=dict(definition.custom_attributes),
    )


def _minimal_state(client):
    state = _default_state(client)
    state.piece_definitions = build_catalog_piece_definitions()
    state.configuration.enabled_piece_types = list(state.piece_definitions)
    state.board.grid = [
        [None for _ in range(state.board.cols)] for _ in range(state.board.rows)
    ]
    state.board.grid[0][7] = _piece(state, "king", "black")
    state.board.grid[7][7] = _piece(state, "king", "white")
    state.current_player = "white"
    state.phase = "play"
    state.game_status = "active"
    state.winner = None
    state.result = None
    state.history = []
    state.captured_pieces = {"white": [], "black": []}
    state.score = {"white": 0, "black": 0}
    state.spent_score = {"white": 0, "black": 0}
    state.turn_counts = {"white": 0, "black": 0}
    state.classic = ClassicRuleState()
    return state


def _resource_value(state, engine: RuleEngine, ability_id: str, params: dict[str, int]):
    configured = state.clone()
    configured.configuration.special_abilities.enabled = True
    configured.configuration.special_abilities.allowed = [ability_id]
    configured.configuration.special_abilities.parameters = {ability_id: params}
    configured.abilities.selected["white"] = [ability_id]
    configured.abilities.selected["black"] = []
    return ChassEvaluator(engine).evaluate(configured, detailed=False).values[
        "special_resources"
    ]["white"]


def test_chass_coverage_contract_matches_the_live_catalog_and_rule_engine():
    definitions = build_catalog_piece_definitions()
    piece_parameters = {
        piece_type: {
            parameter["id"]
            for parameter in definition.custom_attributes.get("tunableParameters", [])
        }
        for piece_type, definition in definitions.items()
        if definition.custom_attributes.get("tunableParameters")
    }
    ability_parameters = {
        ability["id"]: {
            parameter["id"] for parameter in ability.get("tunableParameters", [])
        }
        for ability in SPECIAL_ABILITIES
    }

    assert piece_parameters == {
        piece_type: set(parameters)
        for piece_type, parameters in PIECE_PARAMETER_COVERAGE.items()
    }
    assert ability_parameters == {
        ability_id: set(parameters)
        for ability_id, parameters in ABILITY_PARAMETER_COVERAGE.items()
    }
    assert {mode["id"] for mode in VICTORY_MODES} == set(VICTORY_MODE_COVERAGE)
    assert {rule.id for rule in RuleEngine().available_rules()} == set(
        RULE_EVALUATION_COVERAGE
    )


@pytest.mark.parametrize(
    ("piece_type", "parameter", "low", "high"),
    [
        ("maharani", "blockersCrossed", 1, 2),
        ("catapult", "movementDistance", 1, 2),
        ("catapult", "shortProjectileSkip", 1, 2),
        ("catapult", "shortRecoveryTurns", 2, 8),
        ("catapult", "longProjectileSkip", 2, 3),
        ("catapult", "longRecoveryTurns", 4, 10),
        ("hypnotizer", "movementDistance", 2, 3),
        ("hypnotizer", "weakContactTurns", 3, 8),
        ("hypnotizer", "mediumContactTurns", 4, 8),
        ("hypnotizer", "strongContactTurns", 5, 8),
        ("diplomat", "movementDistance", 1, 2),
        ("diplomat", "contactTurns", 2, 4),
        ("diplomat", "pacifiedTurns", 5, 8),
        ("diplomat", "retireAfterPacifications", 5, 8),
        ("cannibal", "movementDistance", 1, 2),
        ("cannibal", "consumeDistance", 1, 2),
        ("cannibal", "borrowedMovementMoves", 5, 8),
        ("elephant", "movementDistance", 4, 5),
        ("elephant", "chargeDistance", 2, 3),
        ("elephant", "alliedChargeLimit", 1, 2),
    ],
)
def test_every_colored_custom_piece_parameter_changes_intrinsic_utility(
    client,
    piece_type: str,
    parameter: str,
    low: int,
    high: int,
):
    state = _minimal_state(client)
    piece = _piece(state, piece_type, "white")
    state.configuration.piece_parameters = {piece_type: {parameter: low}}
    low_value = intrinsic_piece_value(state, piece)
    state.configuration.piece_parameters = {piece_type: {parameter: high}}
    high_value = intrinsic_piece_value(state, piece)

    assert low_value != high_value
    if piece_type == "maharani":
        assert high_value > low_value


def test_barricade_range_movement_and_rook_demolition_affect_terrain_utility(client):
    state = _minimal_state(client)
    state.board.grid[3][3] = _piece(state, "barricade", "neutral")
    state.board.grid[3][0] = _piece(state, "rook", "white")
    state.board.grid[1][3] = _piece(state, "pawn", "white")
    evaluator = ChassEvaluator(RuleEngine())

    state.configuration.piece_parameters = {
        "barricade": {"movementDistance": 1, "controlRange": 1}
    }
    short_range = evaluator.evaluate(state, detailed=False).values["terrain"]["white"]
    state.configuration.piece_parameters = {
        "barricade": {"movementDistance": 1, "controlRange": 2}
    }
    controlled = evaluator.evaluate(state, detailed=False).values["terrain"]["white"]
    state.configuration.piece_parameters = {
        "barricade": {"movementDistance": 4, "controlRange": 2}
    }
    mobile = evaluator.evaluate(state, detailed=False).values["terrain"]["white"]

    assert short_range >= 0.5  # The unobstructed Rook can demolish the Barricade.
    assert controlled > short_range
    assert mobile > controlled


@pytest.mark.parametrize(
    ("ability_id", "parameter", "low", "high"),
    [
        ("necromancy", "cooldownTurns", 1, 10),
        ("getaway", "usesPerGame", 1, 2),
        ("eye_for_an_eye", "cooldownTurns", 1, 10),
        ("kamikaze", "blastRadius", 1, 4),
        ("episcopal", "cooldownTurns", 1, 10),
        ("episcopal", "shiftDistance", 1, 3),
        ("power_of_love", "durationTurns", 1, 20),
        ("scorch", "cooldownTurns", 1, 10),
        ("scorch", "usesPerGame", 1, 4),
        ("scorch", "minimumGap", 0, 3),
    ],
)
def test_every_special_ability_parameter_changes_resource_utility(
    client,
    ability_id: str,
    parameter: str,
    low: int,
    high: int,
):
    state = _default_state(client)
    state.piece_definitions = build_catalog_piece_definitions()
    if ability_id == "necromancy":
        state.captured_pieces["white"].append(_piece(state, "queen", "black"))
        state.score["white"] = 10
        state.board.grid[6][0] = None
    engine = RuleEngine()

    low_value = _resource_value(state, engine, ability_id, {parameter: low})
    high_value = _resource_value(state, engine, ability_id, {parameter: high})

    assert low_value != high_value


def test_configured_points_only_change_tactics_when_the_win_condition_uses_score(client):
    state = _minimal_state(client)
    state.board.grid[4][0] = _piece(state, "rook", "white")
    target = _piece(state, "pawn", "black", points=1)
    state.board.grid[4][4] = target
    evaluator = ChassEvaluator(RuleEngine())

    classic_low = evaluator.evaluate(state, detailed=False).values["tactical_pressure"][
        "white"
    ]
    target.points = 20
    classic_high = evaluator.evaluate(state, detailed=False).values["tactical_pressure"][
        "white"
    ]

    state.configuration.victory.mode = "point_race"
    target.points = 1
    race_low = evaluator.evaluate(state, detailed=False).values["tactical_pressure"][
        "white"
    ]
    target.points = 20
    race_high = evaluator.evaluate(state, detailed=False).values["tactical_pressure"][
        "white"
    ]

    assert classic_low == classic_high
    assert race_high > race_low


@pytest.mark.parametrize("victory_mode", sorted(VICTORY_MODE_COVERAGE))
def test_every_win_condition_produces_a_finite_explained_evaluation(
    client,
    victory_mode: str,
):
    state = _default_state(client)
    state.configuration.victory.mode = victory_mode
    if victory_mode == "timed":
        state.clock = ClockState(
            initial_seconds=600,
            remaining_seconds={"white": 480, "black": 420},
            active_color="white",
            turn_started_at=datetime.now(timezone.utc),
        )

    result = ChassEvaluator(RuleEngine()).evaluate(state)

    assert math.isfinite(result.score)
    assert result.factors[0].id == "goal_progress"
    assert result.factors[0].label == "Win Condition"


def test_position_hash_tracks_rule_parameters_runtime_and_model_version(client):
    state = _default_state(client)
    baseline = chass_position_hash(state)
    state.configuration.custom_rules.affinity_enabled = True
    configured = chass_position_hash(state)
    state.affinity.command_points["white"] = 2
    runtime = chass_position_hash(state)

    assert MODEL_VERSION.startswith("chass-hce-")
    assert len({baseline, configured, runtime}) == 3


def test_rule_engine_turn_simulation_is_immutable_and_clock_safe(client):
    state = _default_state(client)
    state.clock = ClockState(
        initial_seconds=600,
        remaining_seconds={"white": 579.25, "black": 588.5},
        active_color="white",
        turn_started_at=datetime.now(timezone.utc),
    )
    before = state.model_dump(mode="json")
    engine = RuleEngine()

    child = engine.simulate_turn_move(
        state,
        Move(fromRow=6, fromCol=4, toRow=4, toCol=4),
    )

    assert state.model_dump(mode="json") == before
    assert child.current_player == "black"
    assert child.clock is not None
    assert child.clock.remaining_seconds == {"white": 579.25, "black": 588.5}
    assert len(child.history) == 1


def test_action_space_includes_moves_special_actions_and_affinity_powers(client):
    state = _default_state(client)
    state.configuration.custom_rules.affinity_enabled = True
    state.affinity.command_points["white"] = 3
    state.configuration.special_abilities.enabled = True
    state.configuration.special_abilities.allowed = ["scorch"]
    state.abilities.selected["white"] = ["scorch"]

    actions = legal_turn_actions(state, RuleEngine())
    kinds = {action.kind for action in actions}
    custom_types = {
        action.payload.get("actionType")
        for action in actions
        if action.payload is not None
    }

    assert "move" in kinds
    assert "custom" in kinds
    assert "command" in kinds
    assert "scorch" in custom_types


def test_search_detects_an_authoritative_checkmate_in_one(client):
    state = _minimal_state(client)
    state.board.grid = [
        [None for _ in range(state.board.cols)] for _ in range(state.board.rows)
    ]
    state.board.grid[0][0] = _piece(state, "king", "black")
    state.board.grid[2][2] = _piece(state, "king", "white")
    state.board.grid[2][1] = _piece(state, "queen", "white")
    engine = RuleEngine()
    engine.evaluate_state(state)

    result = asyncio.run(
        ChassAnalysisProvider(engine, movetime_ms=300).analyze(state)
    )

    assert result.immediate_winner == "white"
    assert result.mate_in == 1
    assert result.white_share == 1


def test_every_finished_result_without_a_winner_is_an_analysis_draw(client):
    state = _minimal_state(client)
    state.phase = "finished"
    state.game_status = "points"
    engine = RuleEngine()
    evaluator = ChassEvaluator(engine)

    assert evaluator.evaluate(state, detailed=False).score == 0
    assert ChassSearch(engine, evaluator).analyze(state).score == 0
    outcome = MatchAnalysisService._terminal_outcome(state)
    assert outcome is not None
    assert outcome.whiteWin == 0
    assert outcome.draw == 1
    assert outcome.blackWin == 0
    assert MatchAnalysisService._terminal_label(state) == "draw"


def test_legacy_gambit_creation_enables_native_analysis_by_default(client):
    response = client.post(
        "/game/create",
        json={"mode": "local", "variant": "gambit"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["game"]["configuration"]["matchPredictorEnabled"] is True


def test_custom_profile_service_returns_cached_native_analysis(client):
    state = _default_state(client)
    state.configuration.custom_rules.affinity_enabled = True
    selection = select_analysis_profile(state)
    assert selection.profile is not None
    assert selection.profile.engine_id == "chass"

    external = IdleStockfishProvider()
    engine = RuleEngine()
    service = MatchAnalysisService(
        external,
        engine,
        chass_provider=ChassAnalysisProvider(engine, movetime_ms=40),
    )

    async def scenario():
        compatibility = await service.configuration_compatibility(state, verify=True)
        assert compatibility.status == "compatible"
        assert compatibility.engineId == "chass"
        assert compatibility.parityChecked is False

        pending = await service.request(state, version=4)
        assert pending.status == "analyzing"
        assert pending.engineId == "chass"
        await service.wait_for_game(state.id)
        ready = await service.request(state, version=4)
        cached = await service.request(state, version=5)
        await service.shutdown()
        return ready, cached

    ready, cached = asyncio.run(scenario())

    assert external.calls == 0
    assert ready.status == "ready"
    assert ready.engineId == "chass"
    assert ready.modelVersion == MODEL_VERSION
    assert ready.outcome is not None and ready.outcome.draw == 0
    assert ready.factors
    assert cached.positionHash == ready.positionHash
    assert cached.gameVersion == 5


def test_analysis_never_evaluates_hidden_setup_state(client):
    state = _default_state(client)
    state.variant = "gambit"
    state.phase = "deployment"
    state.configuration.match_predictor_enabled = True
    external = IdleStockfishProvider()
    engine = RuleEngine()
    service = MatchAnalysisService(
        external,
        engine,
        chass_provider=ChassAnalysisProvider(engine, movetime_ms=40),
    )

    async def scenario():
        result = await service.request(state, version=2)
        await service.shutdown()
        return result

    result = asyncio.run(scenario())

    assert result.status == "disabled"
    assert result.enabled is True
    assert result.eligible is False
    assert "private setup" in (result.reason or "")
    assert external.calls == 0
