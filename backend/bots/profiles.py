from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BotDifficultyProfile:
    id: str
    target_elo: int
    label: str
    description: str
    native_elo: bool
    candidate_count: int = 1
    top_candidate_count: int = 1
    probe_nodes: int = 0
    rank_nodes: int = 0
    temperature_cp: float = 1.0

    def catalog_view(self) -> dict[str, object]:
        return {
            "id": self.id,
            "targetElo": self.target_elo,
            "label": self.label,
            "description": self.description,
            "engineId": "stockfish",
            "engineName": "Stockfish 18",
            "estimated": True,
        }


# Stockfish 18's native UCI_Elo floor is 1320. Lower profiles use a
# separately calibrated stochastic selector over Stockfish-ranked legal moves.
BOT_PROFILES: tuple[BotDifficultyProfile, ...] = (
    BotDifficultyProfile(
        id="stockfish-500",
        target_elo=500,
        label="Beginner",
        description="Learning the basics",
        native_elo=False,
        candidate_count=14,
        top_candidate_count=3,
        probe_nodes=2_500,
        rank_nodes=6_000,
        temperature_cp=720.0,
    ),
    BotDifficultyProfile(
        id="stockfish-800",
        target_elo=800,
        label="Learner",
        description="Sees simple tactics",
        native_elo=False,
        candidate_count=12,
        top_candidate_count=4,
        probe_nodes=4_000,
        rank_nodes=9_000,
        temperature_cp=460.0,
    ),
    BotDifficultyProfile(
        id="stockfish-1000",
        target_elo=1000,
        label="Developing",
        description="Plays sensible chess",
        native_elo=False,
        candidate_count=10,
        top_candidate_count=4,
        probe_nodes=6_000,
        rank_nodes=14_000,
        temperature_cp=260.0,
    ),
    BotDifficultyProfile(
        id="stockfish-1200",
        target_elo=1200,
        label="Intermediate",
        description="Usually finds solid moves",
        native_elo=False,
        candidate_count=8,
        top_candidate_count=4,
        probe_nodes=9_000,
        rank_nodes=22_000,
        temperature_cp=135.0,
    ),
    BotDifficultyProfile(
        id="stockfish-1500",
        target_elo=1500,
        label="Advanced",
        description="Strong club-level challenge",
        native_elo=True,
    ),
    BotDifficultyProfile(
        id="stockfish-2000",
        target_elo=2000,
        label="Expert",
        description="Punishes most mistakes",
        native_elo=True,
    ),
    BotDifficultyProfile(
        id="stockfish-2500",
        target_elo=2500,
        label="Master",
        description="Elite engine challenge",
        native_elo=True,
    ),
)

BOT_PROFILE_MAP = {profile.id: profile for profile in BOT_PROFILES}


def get_bot_profile(profile_id: str) -> BotDifficultyProfile:
    try:
        return BOT_PROFILE_MAP[profile_id]
    except KeyError as error:
        raise ValueError("Choose one of the available bot difficulties.") from error


def bot_profile_catalog() -> list[dict[str, object]]:
    return [profile.catalog_view() for profile in BOT_PROFILES]
