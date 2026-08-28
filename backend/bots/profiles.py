from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BotDifficultyProfile:
    id: str
    target_elo: int
    label: str
    description: str
    engine_id: str
    engine_name: str
    native_elo: bool
    candidate_count: int = 1
    top_candidate_count: int = 1
    probe_nodes: int = 0
    rank_nodes: int = 0
    temperature_cp: float = 1.0
    movetime_ms: int = 180
    max_root_actions: int = 48
    max_reply_actions: int = 18
    max_quiescence_actions: int = 6
    max_nodes: int = 256
    action_temperature: float = 0.0

    def catalog_view(self) -> dict[str, object]:
        return {
            "id": self.id,
            "targetElo": self.target_elo,
            "label": self.label,
            "description": self.description,
            "engineId": self.engine_id,
            "engineName": self.engine_name,
            "estimated": True,
        }


# Stockfish 18's native UCI_Elo floor is 1320. Lower profiles use a
# separately calibrated stochastic selector over Stockfish-ranked legal moves.
STOCKFISH_BOT_PROFILES: tuple[BotDifficultyProfile, ...] = (
    BotDifficultyProfile(
        id="stockfish-500",
        target_elo=500,
        label="Beginner",
        description="Learning the basics",
        engine_id="stockfish",
        engine_name="Stockfish 18",
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
        engine_id="stockfish",
        engine_name="Stockfish 18",
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
        engine_id="stockfish",
        engine_name="Stockfish 18",
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
        engine_id="stockfish",
        engine_name="Stockfish 18",
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
        engine_id="stockfish",
        engine_name="Stockfish 18",
        native_elo=True,
    ),
    BotDifficultyProfile(
        id="stockfish-2000",
        target_elo=2000,
        label="Expert",
        description="Punishes most mistakes",
        engine_id="stockfish",
        engine_name="Stockfish 18",
        native_elo=True,
    ),
    BotDifficultyProfile(
        id="stockfish-2500",
        target_elo=2500,
        label="Master",
        description="Elite engine challenge",
        engine_id="stockfish",
        engine_name="Stockfish 18",
        native_elo=True,
    ),
)


# The pinned Fairy-Stockfish build exposes native UCI Elo limiting from 500,
# but those ratings are not calibrated across generated Chass variants. Keep
# the public range conservative until self-play data can validate higher levels.
FAIRY_BOT_PROFILES: tuple[BotDifficultyProfile, ...] = (
    BotDifficultyProfile(
        id="fairy-stockfish-500",
        target_elo=500,
        label="Beginner",
        description="Explores unfamiliar variants",
        engine_id="fairy-stockfish",
        engine_name="Fairy-Stockfish",
        native_elo=True,
    ),
    BotDifficultyProfile(
        id="fairy-stockfish-800",
        target_elo=800,
        label="Variant Learner",
        description="Handles basic variant tactics",
        engine_id="fairy-stockfish",
        engine_name="Fairy-Stockfish",
        native_elo=True,
    ),
    BotDifficultyProfile(
        id="fairy-stockfish-1000",
        target_elo=1000,
        label="Variant Challenger",
        description="A steadier static-variant opponent",
        engine_id="fairy-stockfish",
        engine_name="Fairy-Stockfish",
        native_elo=True,
    ),
)


# Chass ratings describe relative difficulty only. The native evaluator is
# intentionally conservative and remains much weaker than either Stockfish.
CHASS_BOT_PROFILES: tuple[BotDifficultyProfile, ...] = (
    BotDifficultyProfile(
        id="chass-500",
        target_elo=500,
        label="Variant Explorer",
        description="Learns unusual pieces and powers",
        engine_id="chass",
        engine_name="Chass Engine",
        native_elo=False,
        candidate_count=5,
        movetime_ms=110,
        max_root_actions=32,
        max_reply_actions=10,
        max_quiescence_actions=4,
        max_nodes=128,
        action_temperature=1.35,
    ),
    BotDifficultyProfile(
        id="chass-800",
        target_elo=800,
        label="Variant Tactician",
        description="Uses deeper custom-rule search",
        engine_id="chass",
        engine_name="Chass Engine",
        native_elo=False,
        candidate_count=1,
        movetime_ms=260,
        max_root_actions=56,
        max_reply_actions=22,
        max_quiescence_actions=8,
        max_nodes=512,
    ),
)


BOT_PROFILES: tuple[BotDifficultyProfile, ...] = (
    *STOCKFISH_BOT_PROFILES,
    *FAIRY_BOT_PROFILES,
    *CHASS_BOT_PROFILES,
)

BOT_PROFILE_MAP = {profile.id: profile for profile in BOT_PROFILES}


def get_bot_profile(profile_id: str) -> BotDifficultyProfile:
    try:
        return BOT_PROFILE_MAP[profile_id]
    except KeyError as error:
        raise ValueError("Choose one of the available bot difficulties.") from error


def bot_profile_catalog() -> list[dict[str, object]]:
    return [profile.catalog_view() for profile in BOT_PROFILES]


def bot_profiles_for_engine(engine_id: str) -> tuple[BotDifficultyProfile, ...]:
    return tuple(profile for profile in BOT_PROFILES if profile.engine_id == engine_id)
