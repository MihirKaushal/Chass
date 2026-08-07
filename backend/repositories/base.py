from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from backend.models import GameState


class RepositoryError(Exception):
    pass


class ConcurrentUpdateError(RepositoryError):
    pass


class ExpiredGameError(RepositoryError):
    pass


class InviteClaimError(RepositoryError):
    pass


@dataclass(frozen=True)
class PlayerIdentity:
    game_id: str
    color: str
    role: str


@dataclass(frozen=True)
class GameRecord:
    state: GameState
    mode: str
    version: int
    player_colors: frozenset[str]
    expires_at: datetime | None

    @property
    def ready(self) -> bool:
        return self.mode == "local" or {"white", "black"}.issubset(self.player_colors)


@dataclass(frozen=True)
class MoveAudit:
    move_number: int
    player_color: str
    piece_type: str
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    explanation: str


class GameRepository(Protocol):
    def create_game(
        self,
        state: GameState,
        mode: str,
        expires_at: datetime | None = None,
        host_token_hash: str | None = None,
        invite_token_hash: str | None = None,
        invite_expires_at: datetime | None = None,
    ) -> GameRecord: ...

    def delete_expired_games(self, now: datetime | None = None) -> int: ...

    def get_game(self, game_id: str) -> GameRecord | None: ...

    def get_player(self, game_id: str, token_hash: str) -> PlayerIdentity | None: ...

    def claim_invite(
        self,
        invite_token_hash: str,
        player_token_hash: str,
    ) -> GameRecord: ...

    def replace_invite(
        self,
        game_id: str,
        invite_token_hash: str,
        expires_at: datetime,
    ) -> None: ...

    def save_game(
        self,
        state: GameState,
        expected_version: int,
        audit: MoveAudit | None = None,
    ) -> GameRecord: ...
