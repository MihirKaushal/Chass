from __future__ import annotations

import asyncio
import math
from time import perf_counter

from backend.models import GameState
from backend.rules import RuleEngine

from .evaluator import ChassEvaluator
from .models import ChassEngineResult
from .search import ChassSearch
from .weights import ENGINE_VERSION, MODEL_VERSION


class ChassAnalysisProvider:
    def __init__(
        self,
        rule_engine: RuleEngine,
        *,
        enabled: bool = True,
        movetime_ms: int = 180,
    ) -> None:
        self.enabled = enabled
        self.rule_engine = rule_engine
        self.movetime_ms = max(25, movetime_ms)
        self.engine_name = ENGINE_VERSION
        self.last_error: str | None = None
        self.public_error: str | None = None
        self._evaluator = ChassEvaluator(rule_engine)

    @property
    def ready(self) -> bool:
        return self.enabled

    async def start(self) -> bool:
        return self.enabled

    async def close(self) -> None:
        return None

    @staticmethod
    def _white_share(score: float, state: GameState) -> float:
        area = state.board.rows * state.board.cols
        confidence = 0.84 if area <= 100 else (0.78 if area <= 144 else 0.72)
        logistic = 1 / (1 + math.exp(-max(-20.0, min(20.0, score)) / 2.6))
        return max(0.01, min(0.99, 0.5 + confidence * (logistic - 0.5)))

    def _analyze_sync(self, state: GameState) -> ChassEngineResult:
        started = perf_counter()
        detailed = self._evaluator.evaluate(state, detailed=True)
        search = ChassSearch(
            self.rule_engine,
            self._evaluator,
            movetime_ms=self.movetime_ms,
        ).analyze(state, static_score=detailed.score)
        score = search.score if search.depth > 0 else detailed.score
        if search.immediate_winner == "white":
            white_share = 1.0 if search.mate_in == 1 else 0.99
        elif search.immediate_winner == "black":
            white_share = 0.0 if search.mate_in == -1 else 0.01
        else:
            white_share = self._white_share(score, state)
        elapsed_ms = round((perf_counter() - started) * 1000)
        return ChassEngineResult(
            score=score,
            white_share=white_share,
            mate_in=search.mate_in,
            factors=detailed.factors,
            depth=search.depth,
            nodes=search.nodes,
            elapsed_ms=elapsed_ms,
            engine_version=self.engine_name,
            model_version=MODEL_VERSION,
            immediate_winner=search.immediate_winner,
            diagnostics={
                "staticScore": round(detailed.score, 4),
                "searchedScore": round(score, 4),
            },
        )

    async def analyze(self, state: GameState) -> ChassEngineResult:
        if not self.enabled:
            raise RuntimeError("The Chass analysis engine is disabled")
        try:
            result = await asyncio.to_thread(self._analyze_sync, state.clone())
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.last_error = f"Chass analysis failed: {type(error).__name__}: {error}"
            self.public_error = "The Chass analysis engine could not evaluate this position."
            raise
        self.last_error = None
        self.public_error = None
        return result
