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
        eligible=True,
        engine_id="chass",
        engine_name="Chass Engine",
        reason=(
            "This configuration uses Chass Engine because its custom mechanics cannot "
            "be represented safely by Stockfish or Fairy-Stockfish."
        ),
    )


def _chass_compatibility(reason: str) -> BotCompatibility:
    return BotCompatibility(
        eligible=True,
        status="compatible",
        reason=reason,
        engine_id="chass",
        engine_name="Chass Engine",
        profiles=bot_profiles_for_engine("chass"),
    )


async def verify_bot_compatibility(
    state: GameState | None,
    analysis_service: MatchAnalysisService,
    *,
    verify: bool,
    fallback_to_chass: bool = False,
) -> BotCompatibility:
    if state is None:
        if fallback_to_chass:
            return _chass_compatibility(
                "This valid custom configuration will use Chass Engine."
            )
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
    if selection.engine_id == "chass":
        return _chass_compatibility(
            selection.reason
            or "Chass Engine supports this custom game through the authoritative Rule Engine."
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
        return _chass_compatibility(
            "Fairy-Stockfish verification is unavailable, so Chass Engine will safely "
            "run this game instead."
        )
    if not compatible:
        return _chass_compatibility(
            f"{reason or 'Fairy-Stockfish does not match Chass legal moves.'} "
            "Chass Engine will run this game instead."
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
