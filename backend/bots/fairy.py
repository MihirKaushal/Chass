from __future__ import annotations

from time import perf_counter

from backend.analysis import (
    FairyStockfishUciProvider,
    MatchAnalysisService,
    select_fairy_profile,
)
from backend.bots.base import BotDecision, BotTurnContext
from backend.bots.moves import legal_uci_moves
from backend.bots.profiles import get_bot_profile
from backend.rules import RuleEngine


class FairyStockfishBotEngine:
    engine_id = "fairy-stockfish"

    def __init__(
        self,
        provider: FairyStockfishUciProvider,
        rule_engine: RuleEngine,
        analysis_service: MatchAnalysisService,
    ) -> None:
        self.provider = provider
        self.rule_engine = rule_engine
        self.analysis_service = analysis_service

    async def choose_action(self, context: BotTurnContext) -> BotDecision:
        started = perf_counter()
        profile = get_bot_profile(context.profile_id)
        if profile.engine_id != self.engine_id:
            raise RuntimeError("The selected difficulty does not belong to Fairy-Stockfish.")

        state = context.state.clone()
        selection = select_fairy_profile(state)
        if not selection.eligible or selection.profile is None:
            raise RuntimeError(selection.reason or "This position is not Fairy bot-compatible.")

        compatible, reason, fen = await self.analysis_service.verify_fairy_profile(
            state,
            selection.profile,
        )
        if not compatible:
            raise RuntimeError(reason or "Fairy legal-move parity failed for this position.")

        legal = legal_uci_moves(state, self.rule_engine)
        if not legal:
            raise RuntimeError("The bot has no legal move in this position.")
        result = await self.provider.search_moves(
            fen,
            selection.profile,
            search_moves=sorted(legal),
            multipv=1,
            movetime_ms=self.provider.movetime_ms,
            limit_strength_elo=profile.target_elo,
        )
        move = legal.get(result.best_move or "")
        if move is None:
            raise RuntimeError("Fairy-Stockfish returned a move outside the Chass legal move set.")
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
