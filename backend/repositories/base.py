from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from backend.models import GameState, MoveRecord

DEFAULT_HISTORY_PAGE_SIZE = 50
MAX_HISTORY_PAGE_SIZE = 100
PERSISTED_HISTORY_WINDOW = 100


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
    updated_at: datetime
    expires_at: datetime | None
    history_paged: bool = False
    persistence_revision: Any | None = None

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
    record: MoveRecord | None = None

    @classmethod
    def from_record(cls, record: MoveRecord) -> "MoveAudit":
        return cls(
            move_number=record.move_number,
            player_color=record.player,
            piece_type=record.piece,
            from_row=record.from_row,
            from_col=record.from_col,
            to_row=record.to_row,
            to_col=record.to_col,
            explanation=record.explanation,
            record=record.model_copy(deep=True),
        )

    def as_record(self) -> MoveRecord:
        if self.record is not None:
            return self.record.model_copy(deep=True)
        return MoveRecord(
            move_number=self.move_number,
            player=self.player_color,
            piece=self.piece_type,
            from_row=self.from_row,
            from_col=self.from_col,
            to_row=self.to_row,
            to_col=self.to_col,
            explanation=self.explanation,
        )


@dataclass(frozen=True)
class HistoryPage:
    records: tuple[MoveRecord, ...]
    has_more: bool
    next_before: int | None


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

    def delete_inactive_games(
        self,
        inactive_before: datetime,
        now: datetime | None = None,
    ) -> int: ...

    def delete_game_if_inactive(
        self,
        game_id: str,
        inactive_before: datetime,
        now: datetime | None = None,
    ) -> bool: ...

    def get_game(self, game_id: str) -> GameRecord | None: ...

    def get_history_page(
        self,
        game_id: str,
        history_epoch: int,
        before_move_number: int | None = None,
        limit: int = DEFAULT_HISTORY_PAGE_SIZE,
    ) -> HistoryPage: ...

    def get_player(self, game_id: str, token_hash: str) -> PlayerIdentity | None: ...

    def claim_invite(
        self,
        invite_token_hash: str,
        player_token_hash: str,
        game_expires_at: datetime,
        inactive_before: datetime,
    ) -> GameRecord: ...

    def replace_invite(
        self,
        game_id: str,
        invite_token_hash: str,
        invite_expires_at: datetime,
        game_expires_at: datetime,
    ) -> None: ...

    def save_game(
        self,
        state: GameState,
        expected_version: int,
        audit: MoveAudit | None = None,
        expires_at: datetime | None = None,
        expected_revision: Any | None = None,
        current_record: GameRecord | None = None,
    ) -> GameRecord: ...
