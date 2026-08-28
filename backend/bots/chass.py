from __future__ import annotations

import asyncio
import hashlib
import math
import random
from time import perf_counter

from backend.analysis.chass import ChassEvaluator, ChassSearch, RankedAction
from backend.bots.base import BotDecision, BotTurnContext
from backend.bots.chass_setup import ChassSetupPlanner
from backend.bots.profiles import BotDifficultyProfile, get_bot_profile
from backend.rules import RuleEngine


class ChassBotEngine:
    engine_id = "chass"
    engine_name = "Chass Engine"

    def __init__(self, rule_engine: RuleEngine) -> None:
        self.rule_engine = rule_engine
        self.evaluator = ChassEvaluator(rule_engine)
        self.setup = ChassSetupPlanner(rule_engine)

    @staticmethod
    def _random(context: BotTurnContext) -> random.Random:
        digest = hashlib.sha256(
            f"{context.game_id}:{context.game_version}:{context.profile_id}".encode()
        ).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))

    @staticmethod
    def _choose_ranked_action(
        rankings: tuple[RankedAction, ...],
        profile: BotDifficultyProfile,
        color: str,
        rng: random.Random,
    ):
        if not rankings:
            return None
        winning = [item for item in rankings if item.immediate_winner == color]
        if winning:
            return winning[0].action
        if profile.candidate_count <= 1 or profile.action_temperature <= 0:
            return rankings[0].action

        candidates = rankings[: min(profile.candidate_count, len(rankings))]
        utilities = [item.score if color == "white" else -item.score for item in candidates]
        best = max(utilities)
        weights = [
            math.exp((utility - best) / profile.action_temperature)
            for utility in utilities
        ]
        return rng.choices(candidates, weights=weights, k=1)[0].action

    def _play_decision(
        self,
        context: BotTurnContext,
        profile: BotDifficultyProfile,
        rng: random.Random,
        started: float,
    ) -> BotDecision:
        state = context.state.clone()
        search = ChassSearch(
            self.rule_engine,
            self.evaluator,
            movetime_ms=profile.movetime_ms,
            max_root_actions=profile.max_root_actions,
            max_reply_actions=profile.max_reply_actions,
            max_quiescence_actions=profile.max_quiescence_actions,
            max_nodes=profile.max_nodes,
        ).analyze(state)
        action = self._choose_ranked_action(
            search.ranked_actions,
            profile,
            state.current_player,
            rng,
        )
        if action is None:
            raise RuntimeError("The Chass bot has no legal action in this position.")

        common = {
            "engine_id": self.engine_id,
            "engine_name": self.engine_name,
            "profile_id": profile.id,
            "target_elo": profile.target_elo,
            "elapsed_ms": round((perf_counter() - started) * 1_000),
        }
        if action.kind == "move":
            return BotDecision(move=action.move, **common)
        if action.kind == "custom":
            return BotDecision(
                move=None,
                action_kind="custom",
                payload=dict(action.payload or {}),
                **common,
            )
        return BotDecision(
            move=None,
            action_kind="command",
            payload={
                "power": action.power,
                "row": action.row,
                "col": action.col,
                "evolveTo": action.evolve_to,
            },
            **common,
        )

    def _choose_sync(self, context: BotTurnContext) -> BotDecision:
        started = perf_counter()
        profile = get_bot_profile(context.profile_id)
        if profile.engine_id != self.engine_id:
            raise RuntimeError("The selected difficulty does not belong to Chass Engine.")
        state = context.state.clone()
        if state.bot is None:
            raise RuntimeError("Bot settings are unavailable.")
        color = state.bot.bot_color
        rng = self._random(context)
        common = {
            "move": None,
            "engine_id": self.engine_id,
            "engine_name": self.engine_name,
            "profile_id": profile.id,
            "target_elo": profile.target_elo,
        }

        if state.phase == "ability_selection":
            choices = self.setup.choose_abilities(state, color, profile, rng)
            return BotDecision(
                action_kind="ability_selection",
                payload={"abilityIds": list(choices)},
                elapsed_ms=round((perf_counter() - started) * 1_000),
                **common,
            )
        if state.phase == "draft":
            action, piece_type = self.setup.choose_draft_action(
                state,
                color,
                profile,
                rng,
            )
            return BotDecision(
                action_kind="draft",
                payload={"action": action, "pieceType": piece_type},
                elapsed_ms=round((perf_counter() - started) * 1_000),
                **common,
            )
        if state.phase == "deployment":
            deployment = self.setup.choose_deployment(state, color, profile, rng)
            return BotDecision(
                action_kind="deployment",
                payload={
                    "pieces": [piece.model_dump(mode="json") for piece in deployment]
                },
                elapsed_ms=round((perf_counter() - started) * 1_000),
                **common,
            )
        if state.phase == "play":
            return self._play_decision(context, profile, rng, started)
        raise RuntimeError(f"The Chass bot cannot act during the {state.phase} phase.")

    async def choose_action(self, context: BotTurnContext) -> BotDecision:
        return await asyncio.to_thread(self._choose_sync, context)
