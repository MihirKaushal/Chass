from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from time import monotonic

from backend.analysis.classic import (
    classic_analysis_eligibility,
    classic_position_fen,
    classic_position_hash,
    extract_position_factors,
)
from backend.analysis.stockfish import EngineAnalysis, StockfishUciProvider
from backend.models import GameState
from backend.models.schemas import (
    MatchAnalysisView,
    MatchEvaluationView,
    MatchOutcomeView,
)
from backend.rules import RuleEngine

logger = logging.getLogger(__name__)
AnalysisListener = Callable[[MatchAnalysisView], Awaitable[None]]
ANALYSIS_DEBOUNCE_SECONDS = 0.025


class MatchAnalysisService:
    def __init__(
        self,
        provider: StockfishUciProvider,
        rule_engine: RuleEngine,
        *,
        cache_size: int = 512,
        failure_retry_seconds: float = 3.0,
    ) -> None:
        self.provider = provider
        self.rule_engine = rule_engine
        self.cache_size = max(1, cache_size)
        self.failure_retry_seconds = max(0.1, failure_retry_seconds)
        self._cache: OrderedDict[str, MatchAnalysisView] = OrderedDict()
        self._failures: OrderedDict[
            tuple[str, str],
            tuple[float, MatchAnalysisView],
        ] = OrderedDict()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._task_positions: dict[str, tuple[int, str]] = {}
        self._latest_positions: dict[str, tuple[int, str | None]] = {}
        self._listener: AnalysisListener | None = None

    def set_listener(self, listener: AnalysisListener) -> None:
        self._listener = listener

    async def start(self) -> bool:
        return await self.provider.start()

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._task_positions.clear()
        self._latest_positions.clear()
        self._cache.clear()
        self._failures.clear()
        await self.provider.close()

    def invalidate(self, game_id: str) -> None:
        self._latest_positions.pop(game_id, None)
        self._task_positions.pop(game_id, None)
        task = self._tasks.pop(game_id, None)
        if task is not None and not task.done():
            task.cancel()

    def health_status(self) -> str:
        if not self.provider.enabled:
            return "disabled"
        if self.provider.ready:
            return "ready"
        if self.provider.last_error:
            return "unavailable"
        return "starting"

    def health_reason(self) -> str | None:
        if self.provider.ready:
            return None
        return getattr(self.provider, "public_error", None)

    @staticmethod
    def _disabled_view(
        state: GameState,
        version: int,
        *,
        enabled: bool,
        reason: str | None,
    ) -> MatchAnalysisView:
        return MatchAnalysisView(
            gameId=state.id,
            enabled=enabled,
            eligible=False,
            status="disabled",
            reason=reason,
            gameVersion=version,
        )

    @staticmethod
    def _terminal_outcome(state: GameState) -> MatchOutcomeView | None:
        if state.winner == "white":
            return MatchOutcomeView(whiteWin=1, draw=0, blackWin=0)
        if state.winner == "black":
            return MatchOutcomeView(whiteWin=0, draw=0, blackWin=1)
        if state.game_status in {"stalemate", "draw"}:
            return MatchOutcomeView(whiteWin=0, draw=1, blackWin=0)
        return None

    @staticmethod
    def _normalize_engine_result(
        result: EngineAnalysis,
        side_to_move: str,
    ) -> tuple[MatchEvaluationView, MatchOutcomeView | None]:
        multiplier = 1 if side_to_move == "white" else -1
        centipawns = (
            result.centipawns * multiplier if result.centipawns is not None else None
        )
        mate_in = result.mate_in * multiplier if result.mate_in is not None else None
        evaluation = MatchEvaluationView(
            centipawns=centipawns,
            mateIn=mate_in,
        )

        outcome = None
        if result.win is not None and result.draw is not None and result.loss is not None:
            total = result.win + result.draw + result.loss
            if total > 0:
                if side_to_move == "white":
                    white, draw, black = result.win, result.draw, result.loss
                else:
                    white, draw, black = result.loss, result.draw, result.win
                outcome = MatchOutcomeView(
                    whiteWin=white / total,
                    draw=draw / total,
                    blackWin=black / total,
                )
        elif mate_in is not None:
            outcome = MatchOutcomeView(
                whiteWin=1 if mate_in > 0 else 0,
                draw=0,
                blackWin=1 if mate_in < 0 else 0,
            )
        return evaluation, outcome

    def _cache_result(self, position_hash: str, result: MatchAnalysisView) -> None:
        self._cache[position_hash] = result.model_copy(deep=True)
        self._cache.move_to_end(position_hash)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)

    def _cache_failure(
        self,
        game_id: str,
        position_hash: str,
        result: MatchAnalysisView,
    ) -> None:
        key = (game_id, position_hash)
        self._failures[key] = (
            monotonic() + self.failure_retry_seconds,
            result.model_copy(deep=True),
        )
        self._failures.move_to_end(key)
        while len(self._failures) > self.cache_size:
            self._failures.popitem(last=False)

    async def _publish_if_current(self, result: MatchAnalysisView) -> None:
        if self._latest_positions.get(result.gameId) != (
            result.gameVersion,
            result.positionHash,
        ):
            return
        if self._listener is not None:
            try:
                await self._listener(result)
            except Exception:
                logger.exception("Match Predictor WebSocket broadcast failed")

    async def _analyze(
        self,
        state: GameState,
        version: int,
        position_hash: str,
        fen: str,
    ) -> None:
        try:
            # Let the authoritative move response clear the event loop first, then keep
            # legal-move factor generation off that loop entirely.
            await asyncio.sleep(ANALYSIS_DEBOUNCE_SECONDS)
            factors = await asyncio.to_thread(
                extract_position_factors,
                state,
                self.rule_engine,
            )
            terminal_outcome = self._terminal_outcome(state)
            if terminal_outcome is not None:
                result = MatchAnalysisView(
                    gameId=state.id,
                    enabled=True,
                    eligible=True,
                    status="ready",
                    reason="The game has reached a final result.",
                    gameVersion=version,
                    positionHash=position_hash,
                    outcome=terminal_outcome,
                    factors=factors,
                    engineVersion=self.provider.engine_name,
                    updatedAt=datetime.now(timezone.utc),
                )
            else:
                engine_result = await self.provider.analyze(fen)
                evaluation, outcome = self._normalize_engine_result(
                    engine_result,
                    state.current_player,
                )
                result = MatchAnalysisView(
                    gameId=state.id,
                    enabled=True,
                    eligible=True,
                    status="ready",
                    gameVersion=version,
                    positionHash=position_hash,
                    evaluation=evaluation,
                    outcome=outcome,
                    factors=factors,
                    engineVersion=engine_result.engine_version,
                    updatedAt=datetime.now(timezone.utc),
                )
            self._cache_result(position_hash, result)
            self._failures.pop((state.id, position_hash), None)
            await self._publish_if_current(result)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning("Match Predictor analysis failed: %s", error)
            public_error = getattr(self.provider, "public_error", None)
            unavailable = MatchAnalysisView(
                gameId=state.id,
                enabled=True,
                eligible=True,
                status="unavailable",
                reason=(
                    public_error
                    or "Live analysis is temporarily unavailable. Retry in a moment."
                ),
                gameVersion=version,
                positionHash=position_hash,
                engineVersion=self.provider.engine_name,
                updatedAt=datetime.now(timezone.utc),
            )
            self._cache_failure(state.id, position_hash, unavailable)
            await self._publish_if_current(unavailable)
        finally:
            current_task = asyncio.current_task()
            if self._tasks.get(state.id) is current_task:
                self._tasks.pop(state.id, None)
                self._task_positions.pop(state.id, None)
            if self._latest_positions.get(state.id) == (version, position_hash):
                self._latest_positions.pop(state.id, None)

    async def request(
        self,
        state: GameState,
        version: int,
        *,
        retry_failed: bool = False,
    ) -> MatchAnalysisView:
        eligibility = classic_analysis_eligibility(state)
        if not eligibility.eligible:
            self.invalidate(state.id)
            return self._disabled_view(
                state,
                version,
                enabled=eligibility.enabled,
                reason=eligibility.reason,
            )

        position_hash = classic_position_hash(state)
        cached = self._cache.get(position_hash)
        if cached is not None:
            self._cache.move_to_end(position_hash)
            return cached.model_copy(
                deep=True,
                update={"gameId": state.id, "gameVersion": version},
            )

        failure_key = (state.id, position_hash)
        if retry_failed:
            self._failures.pop(failure_key, None)
        failed_entry = self._failures.get(failure_key)
        if failed_entry is not None and failed_entry[0] <= monotonic():
            self._failures.pop(failure_key, None)
            failed_entry = None
        if failed_entry is not None:
            self._failures.move_to_end(failure_key)
            failed = failed_entry[1]
            return failed.model_copy(deep=True, update={"gameVersion": version})

        if not self.provider.enabled:
            return MatchAnalysisView(
                gameId=state.id,
                enabled=True,
                eligible=True,
                status="unavailable",
                reason=(
                    getattr(self.provider, "public_error", None)
                    or "Live analysis is disabled on this server."
                ),
                gameVersion=version,
                positionHash=position_hash,
            )

        task_position = self._task_positions.get(state.id)
        if task_position != (version, position_hash):
            existing_task = self._tasks.get(state.id)
            if existing_task is not None and not existing_task.done():
                existing_task.cancel()
            snapshot = state.clone()
            task = asyncio.create_task(
                self._analyze(
                    snapshot,
                    version,
                    position_hash,
                    classic_position_fen(snapshot),
                )
            )
            self._tasks[state.id] = task
            self._task_positions[state.id] = (version, position_hash)
            self._latest_positions[state.id] = (version, position_hash)

        return MatchAnalysisView(
            gameId=state.id,
            enabled=True,
            eligible=True,
            status="analyzing",
            reason="Analyzing the latest position...",
            gameVersion=version,
            positionHash=position_hash,
            engineVersion=self.provider.engine_name,
        )

    async def wait_for_game(self, game_id: str) -> None:
        task = self._tasks.get(game_id)
        if task is not None:
            await task
