from backend.config import get_settings

from .base import (
    ConcurrentUpdateError,
    ExpiredGameError,
    GameRecord,
    GameRepository,
    InviteClaimError,
    MoveAudit,
    PlayerIdentity,
    RepositoryError,
)
from .firestore_repository import FirestoreGameRepository
from .game_repository import SqlGameRepository


def create_game_repository() -> GameRepository:
    if get_settings().persistence_backend == "firestore":
        return FirestoreGameRepository()
    return SqlGameRepository()


__all__ = [
    "ConcurrentUpdateError",
    "ExpiredGameError",
    "FirestoreGameRepository",
    "GameRecord",
    "GameRepository",
    "InviteClaimError",
    "MoveAudit",
    "PlayerIdentity",
    "RepositoryError",
    "SqlGameRepository",
    "create_game_repository",
]
