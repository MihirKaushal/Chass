from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from backend.analysis import AnalysisProfile, MatchAnalysisService, select_fairy_profile
from backend.bots.classic import classic_bot_eligibility
from backend.bots.profiles import BotDifficultyProfile, bot_profiles_for_engine
from backend.models import GameState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BotEngineSelection:
    eligible: bool
    reason: str | None = None
    engine_id: str | None = None
    engine_name: str | None = None
    analysis_profile: AnalysisProfile | None = None

    @property
    def profiles(self) -> tuple[BotDifficultyProfile, ...]:
        return bot_profiles_for_engine(self.engine_id or "")


@dataclass(frozen=True)
class BotCompatibility:
    eligible: bool
    status: Literal["compatible", "incompatible", "verifying", "unavailable"]
    reason: str | None = None
    engine_id: str | None = None
    engine_name: str | None = None
    profiles: tuple[BotDifficultyProfile, ...] = ()

    def api_view(self) -> dict[str, object]:
        return {
            "eligible": self.eligible,
            "status": self.status,
            "reason": self.reason,
            "engineId": self.engine_id,
            "engineName": self.engine_name,
            "profiles": [profile.catalog_view() for profile in self.profiles],
        }


def select_bot_engine(state: GameState) -> BotEngineSelection:
    classic = classic_bot_eligibility(state)
    if classic.eligible:
        return BotEngineSelection(
            eligible=True,
            engine_id="stockfish",
            engine_name="Stockfish 18",
        )

    fairy = select_fairy_profile(state)
    if fairy.eligible and fairy.profile is not None:
        return BotEngineSelection(
            eligible=True,
            engine_id="fairy-stockfish",
            engine_name="Fairy-Stockfish",
            analysis_profile=fairy.profile,
        )

    return BotEngineSelection(
        eligible=False,
        reason=(
            fairy.reason
            or classic.reason
            or "This configuration is not supported by an available chess bot."
        ),
    )


async def verify_bot_compatibility(
    state: GameState | None,
    analysis_service: MatchAnalysisService,
    *,
    verify: bool,
) -> BotCompatibility:
    if state is None:
        return BotCompatibility(
            eligible=False,
            status="incompatible",
            reason="Finish the board configuration before choosing a chess bot.",
        )

    selection = select_bot_engine(state)
    if not selection.eligible or selection.engine_id is None:
        return BotCompatibility(
            eligible=False,
            status="incompatible",
            reason=selection.reason,
        )

    base = {
        "engine_id": selection.engine_id,
        "engine_name": selection.engine_name,
        "profiles": selection.profiles,
    }
    if selection.engine_id == "stockfish":
        return BotCompatibility(
            **base,
            eligible=True,
            status="compatible",
            reason="Stockfish 18 is available for the exact Classic Chass setup.",
        )
    if not verify or selection.analysis_profile is None:
        return BotCompatibility(
            **base,
            eligible=False,
            status="verifying",
            reason="Fix configuration issues before Fairy move parity can be verified.",
        )

    try:
        compatible, reason, _ = await analysis_service.verify_fairy_profile(
            state,
            selection.analysis_profile,
        )
    except Exception as error:
        logger.warning("Fairy bot compatibility verification unavailable: %s", error)
        return BotCompatibility(
            **base,
            eligible=False,
            status="unavailable",
            reason=(
                getattr(analysis_service.fairy_provider, "public_error", None)
                or "Fairy-Stockfish verification is temporarily unavailable."
            ),
        )
    if not compatible:
        return BotCompatibility(
            **base,
            eligible=False,
            status="incompatible",
            reason=reason or "Fairy-Stockfish does not match Chass legal moves.",
        )
    return BotCompatibility(
        **base,
        eligible=True,
        status="compatible",
        reason=(
            "Fairy-Stockfish matched the Chass legal moves and terminal rules for "
            "this starting position."
        ),
    )
