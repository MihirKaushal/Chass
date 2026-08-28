from __future__ import annotations

from backend.models import GameState
from backend.rules.variant_system import FINISHED_STATUSES


def bot_action_needed(state: GameState) -> bool:
    bot = state.bot
    if bot is None or state.game_status in FINISHED_STATUSES:
        return False
    if state.phase == "ability_selection":
        return (
            state.abilities.active_selection_color == bot.bot_color
            and not state.abilities.selected[bot.bot_color]
        )
    if state.phase == "draft" and state.gambit is not None:
        return (
            state.gambit.draft_active_color == bot.bot_color
            and not state.gambit.draft_passed[bot.bot_color]
        )
    if state.phase == "deployment" and state.gambit is not None:
        return (
            state.gambit.deployment_ready[bot.human_color]
            and not state.gambit.deployment_ready[bot.bot_color]
        )
    return state.phase == "play" and state.current_player == bot.bot_color
