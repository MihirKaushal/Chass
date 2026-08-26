from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from time import monotonic

from backend.analysis.classic import (
    classic_position_fen,
    extract_position_factors,
)
from backend.analysis.fairy import FairyStockfishUciProvider
from backend.analysis.profiles import (
    AnalysisProfile,
    analysis_position_fen,
    analysis_position_hash,
    select_analysis_profile,
)
from backend.analysis.stockfish import EngineAnalysis, StockfishUciProvider
from backend.models import GameState
from backend.models.schemas import (
    MatchAnalysisView,
    MatchEvaluationView,
    MatchOutcomeView,
    MatchPredictorCompatibilityView,
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
        fairy_provider: FairyStockfishUciProvider | None = None,
        cache_size: int = 512,
        failure_retry_seconds: float = 3.0,
    ) -> None:
        self.provider = provider
        self.fairy_provider = fairy_provider
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
        self._parity_cache: OrderedDict[str, tuple[bool, str | None]] = OrderedDict()
        self._listener: AnalysisListener | None = None

    def set_listener(self, listener: AnalysisListener) -> None:
        self._listener = listener

    async def start(self) -> bool:
        # Fairy-Stockfish starts lazily only when a compatible custom profile is used.
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
        self._parity_cache.clear()
        await self.provider.close()
        if self.fairy_provider is not None:
            await self.fairy_provider.close()

    def invalidate(self, game_id: str) -> None:
        self._latest_positions.pop(game_id, None)
        self._task_positions.pop(game_id, None)
        task = self._tasks.pop(game_id, None)
        if task is not None and not task.done():
            task.cancel()

    def health_status(self) -> str:
        providers = [
            provider for provider in (self.provider, self.fairy_provider) if provider is not None
        ]
        if not any(provider.enabled for provider in providers):
            return "disabled"
        if any(provider.ready for provider in providers):
            return "ready"
        if all(provider.last_error for provider in providers if provider.enabled):
            return "unavailable"
        return "starting"

    def health_reason(self) -> str | None:
        if self.provider.ready or (self.fairy_provider and self.fairy_provider.ready):
            return None
        return getattr(self.provider, "public_error", None)

    def health_details(self) -> dict[str, str]:
        def status(provider) -> str:
            if provider is None or not provider.enabled:
                return "disabled"
            if provider.ready:
                return "ready"
            if provider.last_error:
                return "unavailable"
            return "not_started"

        return {
            "stockfish": status(self.provider),
            "fairyStockfish": status(self.fairy_provider),
        }

    @staticmethod
    def _disabled_view(
        state: GameState,
        version: int,
        *,
        enabled: bool,
        reason: str | None,
        profile: AnalysisProfile | None = None,
    ) -> MatchAnalysisView:
        return MatchAnalysisView(
            gameId=state.id,
            enabled=enabled,
            eligible=False,
            status="disabled",
            reason=reason,
            gameVersion=version,
            engineId=profile.engine_id if profile else None,
            engineName=profile.engine_name if profile else None,
            accuracy=profile.accuracy if profile else None,
            calibrated=profile.calibrated if profile else False,
        )

    @staticmethod
    def _profile_fields(profile: AnalysisProfile) -> dict:
        return {
            "engineId": profile.engine_id,
            "engineName": profile.engine_name,
            "accuracy": profile.accuracy,
            "calibrated": profile.calibrated,
        }

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
    def _terminal_label(state: GameState) -> str | None:
        if state.winner in {"white", "black"}:
            return state.winner
        if state.game_status in {"stalemate", "draw"}:
            return "draw"
        return None

    @staticmethod
    def _chass_move_keys(
        state: GameState,
        rule_engine: RuleEngine,
    ) -> frozenset[tuple[int, int, int, int]]:
        if MatchAnalysisService._terminal_label(state) is not None:
            return frozenset()
        return frozenset(
            (move.from_row, move.from_col, move.to_row, move.to_col)
            for move in rule_engine.get_valid_moves_for_current_player(state)
        )

    async def _verify_fairy_parity(
        self,
        state: GameState,
        profile: AnalysisProfile,
        fen: str,
        position_hash: str,
    ) -> tuple[bool, str | None]:
        cached = self._parity_cache.get(position_hash)
        if cached is not None:
            self._parity_cache.move_to_end(position_hash)
            return cached
        if self.fairy_provider is None:
            raise RuntimeError("Fairy-Stockfish is not configured on this server")

        expected_terminal = self._terminal_label(state)
        chass_moves = await asyncio.to_thread(
            self._chass_move_keys,
            state,
            self.rule_engine,
        )
        inspection = await self.fairy_provider.inspect_position(
            fen,
            profile,
            rows=state.board.rows,
            cols=state.board.cols,
            side_to_move=state.current_player,
            probe_terminal=expected_terminal is not None,
        )
        reason = None
        if expected_terminal is not None and inspection.terminal_outcome != expected_terminal:
            reason = (
                "Fairy terminal-outcome parity failed for this position "
                f"(Chass {expected_terminal}, "
                f"Fairy {inspection.terminal_outcome or 'active'})."
            )
        elif expected_terminal is None and inspection.legal_moves != chass_moves:
            reason = (
                "Fairy legal-move parity failed for this position "
                f"(Chass {len(chass_moves)}, Fairy {len(inspection.legal_moves)})."
            )
        elif expected_terminal is None and inspection.terminal_outcome is not None:
            reason = (
                "Fairy terminal-outcome parity failed for this position "
                f"(Chass active, Fairy {inspection.terminal_outcome})."
            )
        result = (reason is None, reason)
        self._parity_cache[position_hash] = result
        self._parity_cache.move_to_end(position_hash)
        while len(self._parity_cache) > self.cache_size:
            self._parity_cache.popitem(last=False)
        return result

    async def configuration_compatibility(
        self,
        state: GameState | None,
        *,
        verify: bool,
    ) -> MatchPredictorCompatibilityView:
        if state is None:
            return MatchPredictorCompatibilityView(
                enabled=False,
                eligible=False,
                status="incompatible",
                reason="Finish the board configuration before selecting an analysis engine.",
            )
        snapshot = state.clone()
        self.rule_engine.evaluate_state(snapshot)
        selection = select_analysis_profile(snapshot, require_enabled=False)
        if not selection.eligible or selection.profile is None:
            return MatchPredictorCompatibilityView(
                enabled=snapshot.configuration.match_predictor_enabled,
                eligible=False,
                status="incompatible",
                reason=selection.reason,
            )
        profile = selection.profile
        base = {
            "enabled": snapshot.configuration.match_predictor_enabled,
            "engineId": profile.engine_id,
            "engineName": profile.engine_name,
            "accuracy": profile.accuracy,
        }
        if profile.engine_id == "stockfish":
            return MatchPredictorCompatibilityView(
                **base,
                eligible=True,
                status="compatible",
                parityChecked=False,
                reason="Preferred engine for compatible standard-rule 8x8 positions.",
            )
        if not verify:
            return MatchPredictorCompatibilityView(
                **base,
                eligible=True,
                status="verifying",
                parityChecked=False,
                reason="Fix configuration issues before Fairy parity verification runs.",
            )
        fen = analysis_position_fen(snapshot, profile)
        position_hash = analysis_position_hash(snapshot, profile, fen)
        try:
            compatible, reason = await self._verify_fairy_parity(
                snapshot,
                profile,
                fen,
                position_hash,
            )
        except Exception as error:
            logger.warning("Fairy compatibility verification unavailable: %s", error)
            return MatchPredictorCompatibilityView(
                **base,
                eligible=True,
                status="unavailable",
                parityChecked=False,
                reason=(
                    getattr(self.fairy_provider, "public_error", None)
                    or "Fairy verification is temporarily unavailable; gameplay is unaffected."
                ),
            )
        return MatchPredictorCompatibilityView(
            **base,
            eligible=compatible,
            status="compatible" if compatible else "incompatible",
            parityChecked=True,
            reason=(
                "Chass and Fairy agree on legal moves and terminal behavior."
                if compatible
                else reason
            ),
        )

    @staticmethod
    def _normalize_engine_result(
        result: EngineAnalysis,
        side_to_move: str,
    ) -> tuple[MatchEvaluationView, MatchOutcomeView | None]:
        multiplier = 1 if side_to_move == "white" else -1
        centipawns = result.centipawns * multiplier if result.centipawns is not None else None
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
        profile: AnalysisProfile,
    ) -> None:
        try:
            # Let the authoritative move response clear the event loop first, then keep
            # legal-move factor generation off that loop entirely.
            await asyncio.sleep(ANALYSIS_DEBOUNCE_SECONDS)
            if profile.engine_id == "fairy-stockfish":
                compatible, parity_reason = await self._verify_fairy_parity(
                    state,
                    profile,
                    fen,
                    position_hash,
                )
                if not compatible:
                    result = self._disabled_view(
                        state,
                        version,
                        enabled=True,
                        reason=parity_reason,
                        profile=profile,
                    )
                    result.positionHash = position_hash
                    self._cache_result(position_hash, result)
                    await self._publish_if_current(result)
                    return

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
                    engineVersion=(
                        self.fairy_provider.engine_name
                        if profile.engine_id == "fairy-stockfish" and self.fairy_provider
                        else self.provider.engine_name
                    ),
                    **self._profile_fields(profile),
                    updatedAt=datetime.now(timezone.utc),
                )
            else:
                if profile.engine_id == "fairy-stockfish":
                    if self.fairy_provider is None:
                        raise RuntimeError("Fairy-Stockfish is not configured on this server")
                    engine_result = await self.fairy_provider.analyze(fen, profile)
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
                    **self._profile_fields(profile),
                    updatedAt=datetime.now(timezone.utc),
                )
            self._cache_result(position_hash, result)
            self._failures.pop((state.id, position_hash), None)
            await self._publish_if_current(result)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning("Match Predictor analysis failed: %s", error)
            active_provider = (
                self.fairy_provider if profile.engine_id == "fairy-stockfish" else self.provider
            )
            public_error = getattr(active_provider, "public_error", None)
            unavailable = MatchAnalysisView(
                gameId=state.id,
                enabled=True,
                eligible=True,
                status="unavailable",
                reason=(
                    public_error or "Live analysis is temporarily unavailable. Retry in a moment."
                ),
                gameVersion=version,
                positionHash=position_hash,
                engineVersion=active_provider.engine_name if active_provider else None,
                **self._profile_fields(profile),
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
        selection = select_analysis_profile(state)
        if not selection.eligible or selection.profile is None:
            self.invalidate(state.id)
            return self._disabled_view(
                state,
                version,
                enabled=selection.enabled,
                reason=selection.reason,
            )
        profile = selection.profile

        fen = (
            classic_position_fen(state)
            if profile.engine_id == "stockfish"
            else analysis_position_fen(state, profile)
        )
        position_hash = analysis_position_hash(state, profile, fen)
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

        active_provider = (
            self.fairy_provider if profile.engine_id == "fairy-stockfish" else self.provider
        )
        if active_provider is None or not active_provider.enabled:
            return MatchAnalysisView(
                gameId=state.id,
                enabled=True,
                eligible=True,
                status="unavailable",
                reason=(
                    getattr(active_provider, "public_error", None)
                    or "Live analysis is disabled on this server."
                ),
                gameVersion=version,
                positionHash=position_hash,
                **self._profile_fields(profile),
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
                    fen,
                    profile,
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
            engineVersion=active_provider.engine_name,
            **self._profile_fields(profile),
        )

    async def wait_for_game(self, game_id: str) -> None:
        task = self._tasks.get(game_id)
        if task is not None:
            await task
