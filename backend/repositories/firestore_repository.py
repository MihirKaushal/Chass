from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from backend.firebase_client import get_firestore_client
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

GAMES = "games"
PLAYERS = "game_players"
INVITES = "game_invites"
MOVES = "moves"
DELETE_BATCH_SIZE = 400
MAX_GAMES_PER_CLEANUP = 100
LAST_SEEN_WRITE_INTERVAL = timedelta(minutes=5)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class FirestoreGameRepository:
    """Firestore persistence adapter; chess behavior remains in RuleEngine."""

    def __init__(self, client=None) -> None:
        self.client = client or get_firestore_client()

    @staticmethod
    def _record_from_data(data: dict[str, Any]) -> GameRecord:
        state_json = data.get("state_json")
        if not isinstance(state_json, str):
            raise RepositoryError("Stored game state is missing or invalid")
        updated_at = _as_utc(data.get("updated_at")) or _as_utc(data.get("created_at"))
        if updated_at is None:
            raise RepositoryError("Stored game activity timestamp is missing or invalid")

        return GameRecord(
            state=GameState.model_validate_json(state_json),
            mode=str(data.get("mode", "local")),
            version=int(data.get("version", 1)),
            player_colors=frozenset(str(color) for color in data.get("player_colors", [])),
            updated_at=updated_at,
            expires_at=_as_utc(data.get("expires_at")),
        )

    @staticmethod
    def _game_document(
        state: GameState,
        mode: str,
        now: datetime,
        expires_at: datetime | None,
        player_colors: list[str],
        active_invite_hash: str | None,
    ) -> dict[str, Any]:
        return {
            "state_json": state.model_dump_json(),
            "mode": mode,
            "version": 1,
            "player_colors": player_colors,
            "active_invite_hash": active_invite_hash,
            "created_at": now,
            "updated_at": now,
            "expires_at": expires_at,
        }

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

        if mode == "online" and (
            not host_token_hash or not invite_token_hash or not invite_expires_at
        ):
            raise ValueError("Online games require host and invite credentials")

        player_colors = ["white"] if mode == "online" else []
        game_data = self._game_document(
            state,
            mode,
            now,
            expires_at,
            player_colors,
            invite_token_hash,
        )
        batch = self.client.batch()
        batch.set(self.client.collection(GAMES).document(state.id), game_data)

        if mode == "online":
            batch.set(
                self.client.collection(PLAYERS).document(host_token_hash),
                {
                    "game_id": state.id,
                    "color": "white",
                    "role": "host",
                    "joined_at": now,
                    "last_seen_at": now,
                },
            )
            batch.set(
                self.client.collection(INVITES).document(invite_token_hash),
                {
                    "game_id": state.id,
                    "target_color": "black",
                    "created_at": now,
                    "expires_at": invite_expires_at,
                    "used_at": None,
                    "revoked_at": None,
                },
            )

        batch.commit()
        return self._record_from_data(game_data)

    def _delete_matching_documents(self, collection_name: str, game_id: str) -> None:
        collection = self.client.collection(collection_name)
        while True:
            snapshots = list(
                collection.where(filter=FieldFilter("game_id", "==", game_id))
                .limit(DELETE_BATCH_SIZE)
                .stream()
            )
            if not snapshots:
                return

            batch = self.client.batch()
            for snapshot in snapshots:
                batch.delete(snapshot.reference)
            batch.commit()

    @staticmethod
    def _is_inactive(
        data: dict[str, Any],
        inactive_before: datetime,
        now: datetime,
    ) -> bool:
        if data.get("deletion_pending") is True:
            return True

        expires_at = _as_utc(data.get("expires_at"))
        updated_at = _as_utc(data.get("updated_at"))
        return (expires_at is not None and expires_at <= now) or (
            updated_at is not None and updated_at <= inactive_before
        )

    def delete_game_if_inactive(
        self,
        game_id: str,
        inactive_before: datetime,
        now: datetime | None = None,
    ) -> bool:
        current = now or datetime.now(timezone.utc)
        game_ref = self.client.collection(GAMES).document(game_id)
        transaction = self.client.transaction()

        @firestore.transactional
        def mark_for_deletion(transaction):
            snapshot = game_ref.get(transaction=transaction)
            if not snapshot.exists:
                return False

            game = snapshot.to_dict() or {}
            if not self._is_inactive(game, inactive_before, current):
                return False

            if game.get("deletion_pending") is not True:
                transaction.update(
                    game_ref,
                    {
                        "deletion_pending": True,
                        "deletion_started_at": current,
                    },
                )
            return True

        if not mark_for_deletion(transaction):
            return False

        for collection_name in (PLAYERS, INVITES, MOVES):
            self._delete_matching_documents(collection_name, game_id)
        game_ref.delete()
        return True

    def delete_inactive_games(
        self,
        inactive_before: datetime,
        now: datetime | None = None,
    ) -> int:
        current = now or datetime.now(timezone.utc)
        games = self.client.collection(GAMES)
        candidate_ids: set[str] = set()

        for field, cutoff in (
            ("expires_at", current),
            ("updated_at", inactive_before),
        ):
            remaining = MAX_GAMES_PER_CLEANUP - len(candidate_ids)
            if remaining <= 0:
                break
            snapshots = games.where(filter=FieldFilter(field, "<=", cutoff)).limit(
                remaining
            )
            candidate_ids.update(snapshot.id for snapshot in snapshots.stream())

        deleted = 0
        for game_id in candidate_ids:
            if self.delete_game_if_inactive(game_id, inactive_before, current):
                deleted += 1

        return deleted

    def get_game(self, game_id: str) -> GameRecord | None:
        snapshot = self.client.collection(GAMES).document(game_id).get()
        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}
        if data.get("deletion_pending") is True:
            raise ExpiredGameError("Game cleanup is in progress")

        expires_at = _as_utc(data.get("expires_at"))
        if expires_at is not None and expires_at <= datetime.now(timezone.utc):
            raise ExpiredGameError("Game has expired")
        return self._record_from_data(data)

    def get_player(self, game_id: str, token_hash: str) -> PlayerIdentity | None:
        player_ref = self.client.collection(PLAYERS).document(token_hash)
        snapshot = player_ref.get()
        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}
        if data.get("game_id") != game_id:
            return None

        now = datetime.now(timezone.utc)
        last_seen_at = _as_utc(data.get("last_seen_at"))
        if last_seen_at is None or now - last_seen_at >= LAST_SEEN_WRITE_INTERVAL:
            player_ref.update({"last_seen_at": now})

        return PlayerIdentity(
            game_id=game_id,
            color=str(data.get("color", "")),
            role=str(data.get("role", "player")),
        )

    def claim_invite(
        self,
        invite_token_hash: str,
        player_token_hash: str,
        game_expires_at: datetime,
        inactive_before: datetime,
    ) -> GameRecord:
        invite_ref = self.client.collection(INVITES).document(invite_token_hash)
        player_ref = self.client.collection(PLAYERS).document(player_token_hash)
        transaction = self.client.transaction()

        @firestore.transactional
        def claim(transaction):
            now = datetime.now(timezone.utc)
            invite_snapshot = invite_ref.get(transaction=transaction)
            if not invite_snapshot.exists:
                raise InviteClaimError("Invite link is invalid")

            invite = invite_snapshot.to_dict() or {}
            if invite.get("revoked_at") is not None:
                raise InviteClaimError("Invite link was replaced")
            if invite.get("used_at") is not None:
                raise InviteClaimError("Invite link has already been used")

            invite_expires_at = _as_utc(invite.get("expires_at"))
            if invite_expires_at is None or invite_expires_at <= now:
                raise InviteClaimError("Invite link has expired")

            game_id = str(invite.get("game_id", ""))
            game_ref = self.client.collection(GAMES).document(game_id)
            game_snapshot = game_ref.get(transaction=transaction)
            if not game_snapshot.exists:
                raise InviteClaimError("Game no longer exists")

            game = game_snapshot.to_dict() or {}
            if game.get("deletion_pending") is True:
                raise InviteClaimError("Game has expired")
            current_expiration = _as_utc(game.get("expires_at"))
            if current_expiration is not None and current_expiration <= now:
                raise InviteClaimError("Game has expired")
            updated_at = _as_utc(game.get("updated_at")) or _as_utc(
                game.get("created_at")
            )
            if updated_at is None or updated_at <= inactive_before:
                raise InviteClaimError("Game has expired due to inactivity")
            if game.get("active_invite_hash") != invite_token_hash:
                raise InviteClaimError("Invite link was replaced")

            target_color = str(invite.get("target_color", "black"))
            player_colors = set(str(color) for color in game.get("player_colors", []))
            if target_color in player_colors:
                raise InviteClaimError("Game already has two players")

            player_colors.add(target_color)
            transaction.set(
                player_ref,
                {
                    "game_id": game_id,
                    "color": target_color,
                    "role": "player",
                    "joined_at": now,
                    "last_seen_at": now,
                },
            )
            transaction.update(invite_ref, {"used_at": now})
            transaction.update(
                game_ref,
                {
                    "player_colors": sorted(player_colors),
                    "active_invite_hash": None,
                    "updated_at": now,
                    "expires_at": game_expires_at,
                },
            )

            updated_game = dict(game)
            updated_game["player_colors"] = sorted(player_colors)
            updated_game["active_invite_hash"] = None
            updated_game["updated_at"] = now
            updated_game["expires_at"] = game_expires_at
            return updated_game

        return self._record_from_data(claim(transaction))

    def replace_invite(
        self,
        game_id: str,
        invite_token_hash: str,
        invite_expires_at: datetime,
        game_expires_at: datetime,
    ) -> None:
        game_ref = self.client.collection(GAMES).document(game_id)
        new_invite_ref = self.client.collection(INVITES).document(invite_token_hash)
        transaction = self.client.transaction()

        @firestore.transactional
        def replace(transaction):
            now = datetime.now(timezone.utc)
            game_snapshot = game_ref.get(transaction=transaction)
            if not game_snapshot.exists:
                raise RepositoryError("Game no longer exists")

            game = game_snapshot.to_dict() or {}
            if game.get("deletion_pending") is True:
                raise RepositoryError("Game has expired")
            current_expiration = _as_utc(game.get("expires_at"))
            if current_expiration is not None and current_expiration <= now:
                raise RepositoryError("Game has expired")
            active_invite_hash = game.get("active_invite_hash")
            old_invite_ref = None
            old_invite_snapshot = None
            if active_invite_hash:
                old_invite_ref = self.client.collection(INVITES).document(active_invite_hash)
                old_invite_snapshot = old_invite_ref.get(transaction=transaction)

            if old_invite_ref is not None and old_invite_snapshot.exists:
                transaction.update(old_invite_ref, {"revoked_at": now})

            transaction.set(
                new_invite_ref,
                {
                    "game_id": game_id,
                    "target_color": "black",
                    "created_at": now,
                    "expires_at": invite_expires_at,
                    "used_at": None,
                    "revoked_at": None,
                },
            )
            transaction.update(
                game_ref,
                {
                    "active_invite_hash": invite_token_hash,
                    "updated_at": now,
                    "expires_at": game_expires_at,
                },
            )

        replace(transaction)

    def save_game(
        self,
        state: GameState,
        expected_version: int,
        audit: MoveAudit | None = None,
        expires_at: datetime | None = None,
    ) -> GameRecord:
        game_ref = self.client.collection(GAMES).document(state.id)
        transaction = self.client.transaction()

        @firestore.transactional
        def save(transaction):
            game_snapshot = game_ref.get(transaction=transaction)
            if not game_snapshot.exists:
                raise ConcurrentUpdateError("Game no longer exists")

            game = game_snapshot.to_dict() or {}
            if game.get("deletion_pending") is True:
                raise ConcurrentUpdateError("Game no longer exists")
            current_expiration = _as_utc(game.get("expires_at"))
            if current_expiration is not None and current_expiration <= datetime.now(
                timezone.utc
            ):
                raise ConcurrentUpdateError("Game has expired")
            current_version = int(game.get("version", 1))
            if current_version != expected_version:
                raise ConcurrentUpdateError(
                    "Game changed on another device. Refreshing will load the latest position."
                )

            now = datetime.now(timezone.utc)
            next_version = expected_version + 1
            transaction.update(
                game_ref,
                {
                    "state_json": state.model_dump_json(),
                    "version": next_version,
                    "updated_at": now,
                    **({"expires_at": expires_at} if expires_at is not None else {}),
                },
            )

            if audit is not None:
                move_ref = self.client.collection(MOVES).document(
                    f"{state.id}_{next_version}"
                )
                transaction.set(
                    move_ref,
                    {
                        "game_id": state.id,
                        "game_version": next_version,
                        "move_number": audit.move_number,
                        "player_color": audit.player_color,
                        "piece_type": audit.piece_type,
                        "from_row": audit.from_row,
                        "from_col": audit.from_col,
                        "to_row": audit.to_row,
                        "to_col": audit.to_col,
                        "explanation": audit.explanation,
                        "created_at": now,
                    },
                )

            updated_game = dict(game)
            updated_game["state_json"] = state.model_dump_json()
            updated_game["version"] = next_version
            updated_game["updated_at"] = now
            if expires_at is not None:
                updated_game["expires_at"] = expires_at
            return updated_game

        return self._record_from_data(save(transaction))
