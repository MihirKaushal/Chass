from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from backend.models import GameState
from backend.rules import RuleEngine

from .action_space import ChassAction, legal_turn_actions, select_search_actions
from .evaluator import ChassEvaluator, chass_position_hash


@dataclass(frozen=True)
class RankedAction:
    action: ChassAction
    score: float
    immediate_winner: str | None = None
    mate_in: int | None = None


@dataclass(frozen=True)
class SearchResult:
    score: float
    depth: int
    nodes: int
    mate_in: int | None = None
    immediate_winner: str | None = None
    best_action: ChassAction | None = None
    ranked_actions: tuple[RankedAction, ...] = ()


class SearchDeadline(Exception):
    pass


class ChassSearch:
    def __init__(
        self,
        engine: RuleEngine,
        evaluator: ChassEvaluator,
        *,
        movetime_ms: int = 180,
        max_root_actions: int = 48,
        max_reply_actions: int = 18,
        max_quiescence_actions: int = 6,
        max_nodes: int = 256,
    ) -> None:
        self.engine = engine
        self.evaluator = evaluator
        self.movetime_ms = max(25, movetime_ms)
        self.max_root_actions = max(8, max_root_actions)
        self.max_reply_actions = max(4, max_reply_actions)
        self.max_quiescence_actions = max(2, max_quiescence_actions)
        self.max_nodes = max(16, max_nodes)
        self._deadline = 0.0
        self._nodes = 0
        self._table: dict[tuple[str, int], float] = {}
        self._prepared_root_children: dict[str, GameState] = {}

    @staticmethod
    def _terminal_score(state: GameState) -> float | None:
        if state.winner == "white":
            return 100.0
        if state.winner == "black":
            return -100.0
        if state.phase == "finished":
            return 0.0
        return None

    def _check_budget(self) -> None:
        if perf_counter() >= self._deadline or self._nodes >= self.max_nodes:
            raise SearchDeadline

    def _apply(self, state: GameState, action: ChassAction) -> GameState | None:
        self._check_budget()
        try:
            child = action.apply(state, self.engine)
        except ValueError:
            return None
        self._nodes += 1
        return child

    @staticmethod
    def _last_turn_was_tactical(state: GameState) -> bool:
        if state.game_status == "check":
            return True
        if not state.history:
            return False
        record = state.history[-1]
        return bool(record.captures) or record.action_type != "move"

    def _quiescence(
        self,
        state: GameState,
        alpha: float,
        beta: float,
        depth: int,
    ) -> float:
        self._check_budget()
        stand_pat = self.evaluator.evaluate(state, detailed=False).score
        maximizing = state.current_player == "white"
        in_check = state.game_status == "check"
        if not in_check:
            if maximizing:
                if stand_pat >= beta:
                    return stand_pat
                alpha = max(alpha, stand_pat)
            else:
                if stand_pat <= alpha:
                    return stand_pat
                beta = min(beta, stand_pat)
        if depth <= 0 or (not in_check and not self._last_turn_was_tactical(state)):
            return stand_pat

        actions = legal_turn_actions(
            state,
            self.engine,
            limit=None if in_check else self.max_quiescence_actions,
        )
        if not in_check:
            actions = [action for action in actions if action.ordering_score >= 4.0]
        best = stand_pat if not in_check else (float("-inf") if maximizing else float("inf"))
        explored = False
        for action in actions:
            child = self._apply(state, action)
            if child is None:
                continue
            explored = True
            terminal = self._terminal_score(child)
            score = (
                terminal
                if terminal is not None
                else self._quiescence(child, alpha, beta, depth - 1)
            )
            if maximizing:
                best = max(best, score)
                alpha = max(alpha, best)
            else:
                best = min(best, score)
                beta = min(beta, best)
            if alpha >= beta:
                break
        return best if explored else stand_pat

    def _search(
        self,
        state: GameState,
        depth: int,
        alpha: float,
        beta: float,
    ) -> float:
        self._check_budget()
        terminal = self._terminal_score(state)
        if terminal is not None:
            return terminal
        if depth <= 0:
            return self._quiescence(state, alpha, beta, depth=1)

        key = (chass_position_hash(state), depth)
        cached = self._table.get(key)
        if cached is not None:
            return cached

        actions = legal_turn_actions(
            state,
            self.engine,
            limit=None if state.game_status == "check" else self.max_reply_actions,
        )
        if not actions:
            value = self.evaluator.evaluate(state, detailed=False).score
            self._table[key] = value
            return value

        maximizing = state.current_player == "white"
        best = float("-inf") if maximizing else float("inf")
        found = False
        for action in actions:
            child = self._apply(state, action)
            if child is None:
                continue
            found = True
            score = self._search(child, depth - 1, alpha, beta)
            if maximizing:
                best = max(best, score)
                alpha = max(alpha, best)
            else:
                best = min(best, score)
                beta = min(beta, best)
            if alpha >= beta:
                break
        if not found:
            best = self.evaluator.evaluate(state, detailed=False).score
        self._table[key] = best
        return best

    @staticmethod
    def _ordered_rankings(
        state: GameState,
        rankings: list[RankedAction],
    ) -> list[RankedAction]:
        maximizing = state.current_player == "white"
        return sorted(
            rankings,
            key=lambda item: (
                -item.score if maximizing else item.score,
                item.action.key,
            ),
        )

    @classmethod
    def _fallback_rankings(
        cls,
        state: GameState,
        actions: list[ChassAction],
        static_score: float,
    ) -> list[RankedAction]:
        """Keep legal root actions usable when a slow host exhausts the search budget."""
        direction = 1.0 if state.current_player == "white" else -1.0
        return cls._ordered_rankings(
            state,
            [
                RankedAction(
                    action=action,
                    score=static_score + (direction * action.ordering_score * 0.001),
                )
                for action in actions
            ],
        )

    def _rank_root_actions(
        self,
        state: GameState,
        actions: list[ChassAction],
        *,
        depth: int,
    ) -> tuple[list[RankedAction], bool]:
        rankings: list[RankedAction] = []
        for action in actions:
            try:
                self._check_budget()
                child = self._prepared_root_children.get(action.key)
                if child is None:
                    child = self._apply(state, action)
                else:
                    self._nodes += 1
                if child is None:
                    continue
                terminal_score = self._terminal_score(child)
                score = (
                    terminal_score
                    if terminal_score is not None
                    else self._search(
                        child,
                        depth - 1,
                        float("-inf"),
                        float("inf"),
                    )
                )
            except SearchDeadline:
                return self._ordered_rankings(state, rankings), False

            immediate_winner = (
                state.current_player
                if child.winner == state.current_player
                else None
            )
            mate_in = None
            if (
                immediate_winner is not None
                and child.result is not None
                and child.result.reason_code == "checkmate"
            ):
                mate_in = 1 if state.current_player == "white" else -1
            rankings.append(
                RankedAction(
                    action=action,
                    score=score,
                    immediate_winner=immediate_winner,
                    mate_in=mate_in,
                )
            )
        return self._ordered_rankings(state, rankings), True

    def _prepare_root_actions(
        self,
        state: GameState,
        actions: list[ChassAction],
    ) -> tuple[list[ChassAction], list[RankedAction], dict[str, float]]:
        """Screen every root action for immediate outcomes before truncation."""
        valid_actions: list[ChassAction] = []
        immediate_wins: list[RankedAction] = []
        priorities: dict[str, float] = {}
        self._prepared_root_children.clear()
        for action in actions:
            try:
                child = action.apply(state, self.engine)
            except ValueError:
                continue
            valid_actions.append(action)
            self._prepared_root_children[action.key] = child
            priority = action.ordering_score
            if child.game_status == "check":
                priority += 25.0
            if child.winner == state.current_player:
                terminal_score = self._terminal_score(child)
                mate_in = None
                if child.result is not None and child.result.reason_code == "checkmate":
                    mate_in = 1 if state.current_player == "white" else -1
                immediate_wins.append(
                    RankedAction(
                        action=action,
                        score=terminal_score if terminal_score is not None else 0.0,
                        immediate_winner=state.current_player,
                        mate_in=mate_in,
                    )
                )
                priority += 1_000.0
            elif child.winner is not None:
                priority -= 1_000.0
            priorities[action.key] = priority
        return valid_actions, self._ordered_rankings(state, immediate_wins), priorities

    def analyze(
        self,
        state: GameState,
        *,
        static_score: float | None = None,
    ) -> SearchResult:
        static = (
            static_score
            if static_score is not None
            else self.evaluator.evaluate(state, detailed=False).score
        )
        terminal = self._terminal_score(state)
        if terminal is not None:
            return SearchResult(terminal, depth=0, nodes=0)

        self._nodes = 0
        self._table.clear()
        try:
            all_actions = legal_turn_actions(state, self.engine)
            valid_actions, immediate_wins, priorities = self._prepare_root_actions(
                state,
                all_actions,
            )
        except Exception:
            return SearchResult(static, depth=0, nodes=0)
        if not valid_actions:
            return SearchResult(static, depth=0, nodes=0)

        if immediate_wins:
            best = immediate_wins[0]
            return SearchResult(
                score=best.score,
                depth=1,
                nodes=0,
                mate_in=best.mate_in,
                immediate_winner=best.immediate_winner,
                best_action=best.action,
                ranked_actions=tuple(immediate_wins),
            )

        actions = select_search_actions(
            valid_actions,
            limit=None if state.game_status == "check" else self.max_root_actions,
            priorities=priorities,
        )
        # Move time is a search budget. Authoritative action generation and
        # terminal screening happen first, so they cannot consume the entire
        # allowance before a single candidate is considered.
        self._deadline = perf_counter() + (self.movetime_ms / 1000)

        rankings, completed = self._rank_root_actions(state, actions, depth=1)
        if not completed:
            # Partial root results are biased by ordering. Keep a legal bot
            # action, but do not report that subset as a completed depth.
            fallback = self._fallback_rankings(state, actions, static)
            return SearchResult(
                static,
                depth=0,
                nodes=self._nodes,
                best_action=fallback[0].action,
                ranked_actions=tuple(fallback),
            )

        if not rankings:
            return SearchResult(static, depth=0, nodes=self._nodes)

        completed_depth = 1
        remaining_fraction = max(
            0.0,
            (self._deadline - perf_counter()) / (self.movetime_ms / 1000),
        )
        if (
            completed
            and len(actions) <= self.max_reply_actions
            and remaining_fraction > 0.35
        ):
            deeper_rankings, deeper_completed = self._rank_root_actions(
                state,
                actions,
                depth=2,
            )
            if deeper_completed and deeper_rankings:
                rankings = deeper_rankings
                completed_depth = 2
        best = rankings[0]
        return SearchResult(
            score=best.score,
            depth=completed_depth,
            nodes=self._nodes,
            mate_in=best.mate_in,
            immediate_winner=best.immediate_winner,
            best_action=best.action,
            ranked_actions=tuple(rankings),
        )
