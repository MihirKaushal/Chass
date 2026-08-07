from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from backend.db import GameInviteRow, GamePlayerRow, GameRow, MoveRow, session_scope
from backend.models import GameState
from backend.repositories.base import (
    ConcurrentUpdateError,
    ExpiredGameError,
    GameRecord,
    InviteClaimError,
    MoveAudit,
    PlayerIdentity,
    RepositoryError,
)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class SqlGameRepository:
    def _record_from_row(self, session, row: GameRow) -> GameRecord:
        colors = session.scalars(
            select(GamePlayerRow.color).where(GamePlayerRow.game_id == row.id)
        ).all()
        return GameRecord(
            state=GameState.model_validate_json(row.state_json),
            mode=row.mode,
            version=row.version,
            player_colors=frozenset(colors),
            expires_at=_as_utc(row.expires_at),
        )

    def create_game(
        self,
        state: GameState,
        mode: str,
        expires_at: datetime | None = None,
        host_token_hash: str | None = None,
        invite_token_hash: str | None = None,
        invite_expires_at: datetime | None = None,
    ) -> GameRecord:
        now = datetime.now(timezone.utc)
        self.delete_expired_games(now)

        with session_scope() as session:
            game_row = GameRow(
                id=state.id,
                mode=mode,
                state_json=state.model_dump_json(),
                version=1,
                created_at=now,
                updated_at=now,
                expires_at=expires_at,
            )
            session.add(game_row)
            session.flush()

            if mode == "online":
                if not host_token_hash or not invite_token_hash or not invite_expires_at:
                    raise ValueError("Online games require host and invite credentials")

                session.add(
                    GamePlayerRow(
                        id=str(uuid.uuid4()),
                        game_id=state.id,
                        color="white",
                        role="host",
                        token_hash=host_token_hash,
                        joined_at=now,
                        last_seen_at=now,
                    )
                )
                session.add(
                    GameInviteRow(
                        id=str(uuid.uuid4()),
                        game_id=state.id,
                        token_hash=invite_token_hash,
                        target_color="black",
                        created_at=now,
                        expires_at=invite_expires_at,
                    )
                )

            session.commit()
            return self._record_from_row(session, game_row)

    def delete_expired_games(self, now: datetime | None = None) -> int:
        cutoff = now or datetime.now(timezone.utc)
        with session_scope() as session:
            result = session.execute(
                delete(GameRow).where(
                    GameRow.expires_at.is_not(None),
                    GameRow.expires_at <= cutoff,
                )
            )
            session.commit()
            return result.rowcount or 0

    def get_game(self, game_id: str) -> GameRecord | None:
        with session_scope() as session:
            row = session.get(GameRow, game_id)
            if row is None:
                return None

            expires_at = _as_utc(row.expires_at)
            if expires_at is not None and expires_at <= datetime.now(timezone.utc):
                raise ExpiredGameError("Game has expired")

            return self._record_from_row(session, row)

    def get_player(self, game_id: str, token_hash: str) -> PlayerIdentity | None:
        with session_scope() as session:
            player = session.scalar(
                select(GamePlayerRow).where(
                    GamePlayerRow.game_id == game_id,
                    GamePlayerRow.token_hash == token_hash,
                )
            )
            if player is None:
                return None

            player.last_seen_at = datetime.now(timezone.utc)
            session.commit()
            return PlayerIdentity(game_id=player.game_id, color=player.color, role=player.role)

    def claim_invite(self, invite_token_hash: str, player_token_hash: str) -> GameRecord:
        now = datetime.now(timezone.utc)

        try:
            with session_scope() as session:
                invite = session.scalar(
                    select(GameInviteRow)
                    .where(GameInviteRow.token_hash == invite_token_hash)
                    .with_for_update()
                )
                if invite is None:
                    raise InviteClaimError("Invite link is invalid")
                if invite.revoked_at is not None:
                    raise InviteClaimError("Invite link was replaced")
                if invite.used_at is not None:
                    raise InviteClaimError("Invite link has already been used")
                if _as_utc(invite.expires_at) <= now:
                    raise InviteClaimError("Invite link has expired")

                game = session.get(GameRow, invite.game_id)
                if game is None:
                    raise InviteClaimError("Game no longer exists")
                game_expires_at = _as_utc(game.expires_at)
                if game_expires_at is not None and game_expires_at <= now:
                    raise InviteClaimError("Game has expired")

                occupied = session.scalar(
                    select(GamePlayerRow).where(
                        GamePlayerRow.game_id == invite.game_id,
                        GamePlayerRow.color == invite.target_color,
                    )
                )
                if occupied is not None:
                    raise InviteClaimError("Game already has two players")

                session.add(
                    GamePlayerRow(
                        id=str(uuid.uuid4()),
                        game_id=invite.game_id,
                        color=invite.target_color,
                        role="player",
                        token_hash=player_token_hash,
                        joined_at=now,
                        last_seen_at=now,
                    )
                )
                invite.used_at = now
                game.updated_at = now
                session.commit()
                return self._record_from_row(session, game)
        except IntegrityError as error:
            raise InviteClaimError("Game already has two players") from error

    def replace_invite(
        self,
        game_id: str,
        invite_token_hash: str,
        expires_at: datetime,
    ) -> None:
        now = datetime.now(timezone.utc)

        with session_scope() as session:
            existing = session.scalars(
                select(GameInviteRow).where(
                    GameInviteRow.game_id == game_id,
                    GameInviteRow.used_at.is_(None),
                    GameInviteRow.revoked_at.is_(None),
                )
            ).all()
            for invite in existing:
                invite.revoked_at = now

            session.add(
                GameInviteRow(
                    id=str(uuid.uuid4()),
                    game_id=game_id,
                    token_hash=invite_token_hash,
                    target_color="black",
                    created_at=now,
                    expires_at=expires_at,
                )
            )
            session.commit()

    def save_game(
        self,
        state: GameState,
        expected_version: int,
        audit: MoveAudit | None = None,
    ) -> GameRecord:
        now = datetime.now(timezone.utc)
        next_version = expected_version + 1

        with session_scope() as session:
            result = session.execute(
                update(GameRow)
                .where(
                    GameRow.id == state.id,
                    GameRow.version == expected_version,
                )
                .values(
                    state_json=state.model_dump_json(),
                    version=next_version,
                    updated_at=now,
                )
            )

            if result.rowcount != 1:
                session.rollback()
                raise ConcurrentUpdateError(
                    "Game changed on another device. Refreshing will load the latest position."
                )

            if audit is not None:
                session.add(
                    MoveRow(
                        id=str(uuid.uuid4()),
                        game_id=state.id,
                        game_version=next_version,
                        move_number=audit.move_number,
                        player_color=audit.player_color,
                        piece_type=audit.piece_type,
                        from_row=audit.from_row,
                        from_col=audit.from_col,
                        to_row=audit.to_row,
                        to_col=audit.to_col,
                        explanation=audit.explanation,
                        created_at=now,
                    )
                )

            session.commit()
            row = session.get(GameRow, state.id)
            if row is None:
                raise RepositoryError("Game disappeared after it was saved")
            return self._record_from_row(session, row)
