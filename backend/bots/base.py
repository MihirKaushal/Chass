from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.models import GameState, Move


@dataclass(frozen=True)
class BotTurnContext:
    game_id: str
    game_version: int
    state: GameState
    profile_id: str


@dataclass(frozen=True)
class BotDecision:
    move: Move
    engine_id: str
    engine_name: str
    profile_id: str
    target_elo: int
    elapsed_ms: int


class BotEngine(Protocol):
    async def choose_action(self, context: BotTurnContext) -> BotDecision: ...
