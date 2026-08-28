from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from time import perf_counter

from backend.analysis.classic import (
    CLASSIC_POINTS,
    CLASSIC_TYPES,
    DISABLED_CLASSIC_RULES,
    REQUIRED_CLASSIC_RULES,
    classic_position_fen,
    definitions_use_classic_behavior,
)
from backend.analysis.stockfish import EngineMoveCandidate, StockfishUciProvider
from backend.bots.base import BotDecision, BotTurnContext
from backend.bots.profiles import BotDifficultyProfile, get_bot_profile
from backend.catalog import classic_layout
from backend.models import GameState, Move
from backend.rules import RuleEngine

PROMOTION_TO_UCI = {
    "queen": "q",
    "rook": "r",
    "bishop": "b",
    "knight": "n",
}


@dataclass(frozen=True)
class ClassicBotEligibility:
    eligible: bool
    reason: str | None = None


def _placement_signature(placement: dict) -> tuple[int, int, str, str]:
    return (
        int(placement["row"]),
        int(placement["col"]),
        str(placement["type"]),
        str(placement["color"]),
    )


def _current_board_signature(state: GameState) -> set[tuple[int, int, str, str]]:
    return {
        (row, col, piece.type, piece.color)
        for row, board_row in enumerate(state.board.grid)
        for col, piece in enumerate(board_row)
        if piece is not None
    }


def classic_bot_eligibility(
    state: GameState,
    *,
    require_initial_position: bool = True,
) -> ClassicBotEligibility:
    if state.variant != "classic" or state.gambit is not None:
        return ClassicBotEligibility(False, "Bots currently support Classic Chass only.")
    if state.board.rows != 8 or state.board.cols != 8:
        return ClassicBotEligibility(False, "Classic bot games require an 8x8 board.")
    if set(state.configuration.enabled_piece_types) != set(CLASSIC_TYPES):
        return ClassicBotEligibility(False, "Classic bot games require all six classic pieces.")
    if state.configuration.piece_parameters and any(
        state.configuration.piece_parameters.values()
    ):
        return ClassicBotEligibility(False, "Classic piece behavior cannot be modified.")
    if not definitions_use_classic_behavior(state):
        return ClassicBotEligibility(False, "Classic piece movement cannot be modified.")
    if any(
        state.piece_definitions[piece_type].points
        != (None if piece_type == "king" else CLASSIC_POINTS[piece_type])
        for piece_type in CLASSIC_TYPES
    ):
        return ClassicBotEligibility(False, "Classic piece point values are required.")
    if state.configuration.victory.mode != "checkmate":
        return ClassicBotEligibility(False, "Classic checkmate must be the win condition.")
    if state.configuration.custom_rules.affinity_enabled:
        return ClassicBotEligibility(False, "Custom rules are not available in bot games yet.")
    if state.configuration.special_abilities.enabled:
        return ClassicBotEligibility(False, "Special abilities are not available in bot games yet.")
    if state.terrain:
        return ClassicBotEligibility(False, "Board terrain is not available in bot games yet.")

    settings = {setting.id: setting for setting in state.rules}
    if any(
        rule_id not in settings or not settings[rule_id].enabled
        for rule_id in REQUIRED_CLASSIC_RULES
    ):
        return ClassicBotEligibility(False, "All required Classic rules must remain enabled.")
    if any(settings.get(rule_id) and settings[rule_id].enabled for rule_id in DISABLED_CLASSIC_RULES):
        return ClassicBotEligibility(False, "Variant rules are not available in bot games yet.")
    if any(setting.params for setting in settings.values()):
        return ClassicBotEligibility(False, "Rule parameters cannot be modified for bot games yet.")

    if require_initial_position:
        expected = {_placement_signature(item) for item in classic_layout(8, 8)}
        configured = {
            _placement_signature(item)
            for item in state.configuration.initial_layout
        }
        if configured != expected or _current_board_signature(state) != expected:
            return ClassicBotEligibility(
                False,
                "Classic bot games require the standard starting formation.",
            )
        if state.history or state.current_player != "white":
            return ClassicBotEligibility(False, "Start a new Classic position to play a bot.")
        if any(
            piece.has_moved
            for row in state.board.grid
            for piece in row
            if piece is not None
        ):
            return ClassicBotEligibility(False, "Starting pieces must be unmoved.")

    return ClassicBotEligibility(True)


def _square_name(row: int, col: int) -> str:
    return f"{chr(ord('a') + col)}{8 - row}"


def move_to_uci(move: Move) -> str:
    suffix = PROMOTION_TO_UCI.get(move.promotion or "", "")
    return (
        f"{_square_name(move.from_row, move.from_col)}"
        f"{_square_name(move.to_row, move.to_col)}{suffix}"
    )


def _legal_uci_moves(state: GameState, rule_engine: RuleEngine) -> dict[str, Move]:
    legal: dict[str, Move] = {}
    for option in rule_engine.get_valid_moves_for_current_player(state):
        piece = state.board.grid[option.from_row][option.from_col]
        promotions: tuple[str | None, ...] = (None,)
        if piece is not None and piece.type == "pawn" and option.to_row in {0, 7}:
            promotions = ("queen", "rook", "bishop", "knight")
        for promotion in promotions:
            move = Move(
                fromRow=option.from_row,
                fromCol=option.from_col,
                toRow=option.to_row,
                toCol=option.to_col,
                promotion=promotion,
            )
            if rule_engine.validate_move(state, move).is_valid:
                legal[move_to_uci(move)] = move
    return legal


def _candidate_score(candidate: EngineMoveCandidate) -> int:
    if candidate.mate_in is not None:
        distance = min(abs(candidate.mate_in), 99)
        return (100_000 - distance * 1_000) if candidate.mate_in > 0 else (-100_000 + distance * 1_000)
    return candidate.centipawns or 0


def _seeded_random(context: BotTurnContext) -> random.Random:
    digest = hashlib.sha256(
        f"{context.game_id}:{context.game_version}:{context.profile_id}".encode("utf-8")
    ).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _weighted_candidate(
    candidates: list[EngineMoveCandidate],
    profile: BotDifficultyProfile,
    rng: random.Random,
) -> EngineMoveCandidate:
    best_score = max(_candidate_score(candidate) for candidate in candidates)
    weights = [
        math.exp(
            -max(0, best_score - _candidate_score(candidate))
            / profile.temperature_cp
        )
        for candidate in candidates
    ]
    return rng.choices(candidates, weights=weights, k=1)[0]


class StockfishClassicBotEngine:
    engine_id = "stockfish"

    def __init__(self, provider: StockfishUciProvider, rule_engine: RuleEngine) -> None:
        self.provider = provider
        self.rule_engine = rule_engine

    async def choose_action(self, context: BotTurnContext) -> BotDecision:
        started = perf_counter()
        profile = get_bot_profile(context.profile_id)
        state = context.state.clone()
        eligibility = classic_bot_eligibility(state, require_initial_position=False)
        if not eligibility.eligible:
            raise RuntimeError(eligibility.reason or "This position is not bot-compatible.")

        legal = _legal_uci_moves(state, self.rule_engine)
        if not legal:
            raise RuntimeError("The bot has no legal move in this position.")
        fen = classic_position_fen(state)

        if profile.native_elo:
            result = await self.provider.search_moves(
                fen,
                search_moves=list(legal),
                multipv=1,
                movetime_ms=self.provider.movetime_ms,
                limit_strength_elo=profile.target_elo,
            )
            chosen_uci = result.best_move
        else:
            rng = _seeded_random(context)
            legal_uci = sorted(legal)
            probe = await self.provider.search_moves(
                fen,
                search_moves=legal_uci,
                multipv=min(profile.top_candidate_count, len(legal_uci)),
                nodes=profile.probe_nodes,
            )
            top_moves = list(dict.fromkeys(
                [candidate.move for candidate in probe.candidates]
                + ([probe.best_move] if probe.best_move else [])
            ))
            remaining = [move for move in legal_uci if move not in top_moves]
            rng.shuffle(remaining)
            candidate_pool = (
                top_moves + remaining
            )[: min(profile.candidate_count, len(legal_uci))]
            ranked = await self.provider.search_moves(
                fen,
                search_moves=candidate_pool,
                multipv=len(candidate_pool),
                nodes=profile.rank_nodes,
            )
            ranked_candidates = [
                candidate
                for candidate in ranked.candidates
                if candidate.move in legal
            ]
            if not ranked_candidates:
                chosen_uci = ranked.best_move or probe.best_move
            else:
                chosen_uci = _weighted_candidate(ranked_candidates, profile, rng).move

        move = legal.get(chosen_uci or "")
        if move is None:
            raise RuntimeError("Stockfish returned a move outside the Chass legal move set.")
        if not self.rule_engine.validate_move(state, move).is_valid:
            raise RuntimeError("The selected bot move failed final rule-engine validation.")

        return BotDecision(
            move=move,
            engine_id=self.engine_id,
            engine_name=self.provider.engine_name,
            profile_id=profile.id,
            target_elo=profile.target_elo,
            elapsed_ms=round((perf_counter() - started) * 1_000),
        )
