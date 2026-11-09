from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from backend.models import GameState, Move

BotActionKind = Literal[
    "move",
    "custom",
    "command",
    "ability_selection",
    "draft",
    "deployment",
]


@dataclass(frozen=True)
class BotTurnContext:
    game_id: str
    game_version: int
    state: GameState
    profile_id: str


@dataclass(frozen=True)
class BotDecision:
    move: Move | None
    engine_id: str
    engine_name: str
    profile_id: str
    target_elo: int
    elapsed_ms: int
    action_kind: BotActionKind = "move"
    payload: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.action_kind == "move" and self.move is None:
            raise ValueError("A move decision requires a move.")
        if self.action_kind != "move" and self.payload is None:
            raise ValueError("A non-move bot decision requires an action payload.")


class BotEngine(Protocol):
    async def choose_action(self, context: BotTurnContext) -> BotDecision: ...
