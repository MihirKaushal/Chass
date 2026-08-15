from backend.config import get_settings

from .base import (
    DEFAULT_HISTORY_PAGE_SIZE,
    MAX_HISTORY_PAGE_SIZE,
    PERSISTED_HISTORY_WINDOW,
    ConcurrentUpdateError,
    ExpiredGameError,
    GameRecord,
    GameRepository,
    HistoryPage,
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
    "DEFAULT_HISTORY_PAGE_SIZE",
    "ExpiredGameError",
    "FirestoreGameRepository",
    "GameRecord",
    "GameRepository",
    "HistoryPage",
    "InviteClaimError",
    "MoveAudit",
    "MAX_HISTORY_PAGE_SIZE",
    "PERSISTED_HISTORY_WINDOW",
    "PlayerIdentity",
    "RepositoryError",
    "SqlGameRepository",
    "create_game_repository",
]
