from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from backend.config import get_settings
from backend.db import GameInviteRow, GamePlayerRow, GameRow, MoveRow, session_scope
from backend.firebase_client import get_firestore_client
from backend.models import GameState
from backend.repositories.base import PERSISTED_HISTORY_WINDOW
from backend.repositories.firestore_repository import (
    GAMES,
    HISTORY_STORAGE_VERSION,
    INVITES,
    MOVES,
    PLAYERS,
)

WRITE_BATCH_SIZE = 400


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _commit_documents(client, documents: list[tuple[str, str, dict[str, Any]]]) -> None:
    for offset in range(0, len(documents), WRITE_BATCH_SIZE):
        batch = client.batch()
        for collection, document_id, data in documents[offset : offset + WRITE_BATCH_SIZE]:
            batch.set(client.collection(collection).document(document_id), data)
        batch.commit()


def _load_documents(
    include_expired: bool = False,
) -> list[tuple[str, str, dict[str, Any]]]:
    documents: list[tuple[str, str, dict[str, Any]]] = []
    now = datetime.now(timezone.utc)
    inactive_before = now - timedelta(hours=get_settings().game_idle_ttl_hours)

    with session_scope() as session:
        games = list(session.scalars(select(GameRow)).all())
        players = list(session.scalars(select(GamePlayerRow)).all())
        invites = list(session.scalars(select(GameInviteRow)).all())
        moves = list(session.scalars(select(MoveRow)).all())

        if not include_expired:
            games = [
                game
                for game in games
                if (game.expires_at is None or _as_utc(game.expires_at) > now)
                and _as_utc(game.updated_at) > inactive_before
            ]

        game_ids = {game.id for game in games}
        players = [player for player in players if player.game_id in game_ids]
        invites = [invite for invite in invites if invite.game_id in game_ids]
        moves = [move for move in moves if move.game_id in game_ids]

        latest_move_rows: dict[tuple[str, int], MoveRow] = {}
        for move in moves:
            key = (move.game_id, move.move_number)
            current = latest_move_rows.get(key)
            if current is None or move.game_version > current.game_version:
                latest_move_rows[key] = move

        colors_by_game: dict[str, set[str]] = defaultdict(set)
        for player in players:
            colors_by_game[player.game_id].add(player.color)

        active_invites: dict[str, GameInviteRow] = {}
        for invite in invites:
            if invite.used_at is not None or invite.revoked_at is not None:
                continue
            current = active_invites.get(invite.game_id)
            if current is None or invite.created_at > current.created_at:
                active_invites[invite.game_id] = invite

        for game in games:
            active_invite = active_invites.get(game.id)
            state = GameState.model_validate_json(game.state_json)
            stored_state = state.model_copy(deep=True)
            stored_state.history = stored_state.history[-PERSISTED_HISTORY_WINDOW:]
            documents.append(
                (
                    GAMES,
                    game.id,
                    {
                        "state_json": stored_state.model_dump_json(),
                        "mode": game.mode,
                        "version": game.version,
                        "history_storage_version": HISTORY_STORAGE_VERSION,
                        "player_colors": sorted(colors_by_game[game.id]),
                        "active_invite_hash": (
                            active_invite.token_hash if active_invite is not None else None
                        ),
                        "created_at": _as_utc(game.created_at),
                        "updated_at": _as_utc(game.updated_at),
                        "expires_at": _as_utc(game.expires_at),
                    },
                )
            )

            for record in state.history:
                source_row = latest_move_rows.get((game.id, record.move_number))
                documents.append(
                    (
                        MOVES,
                        (
                            f"{game.id}_history_{state.history_epoch}_"
                            f"{record.move_number:08d}"
                        ),
                        {
                            "game_id": game.id,
                            "history_key": f"{game.id}:{state.history_epoch}",
                            "history_epoch": state.history_epoch,
                            "game_version": (
                                source_row.game_version
                                if source_row is not None
                                else record.move_number
                            ),
                            "move_number": record.move_number,
                            "player_color": record.player,
                            "piece_type": record.piece,
                            "from_row": record.from_row,
                            "from_col": record.from_col,
                            "to_row": record.to_row,
                            "to_col": record.to_col,
                            "explanation": record.explanation,
                            "action_type": record.action_type,
                            "record_json": record.model_dump_json(),
                            "created_at": (
                                _as_utc(source_row.created_at)
                                if source_row is not None
                                else _as_utc(game.updated_at)
                            ),
                        },
                    )
                )

        for player in players:
            documents.append(
                (
                    PLAYERS,
                    player.token_hash,
                    {
                        "game_id": player.game_id,
                        "color": player.color,
                        "role": player.role,
                        "joined_at": _as_utc(player.joined_at),
                        "last_seen_at": _as_utc(player.last_seen_at),
                    },
                )
            )

        for invite in invites:
            documents.append(
                (
                    INVITES,
                    invite.token_hash,
                    {
                        "game_id": invite.game_id,
                        "target_color": invite.target_color,
                        "created_at": _as_utc(invite.created_at),
                        "expires_at": _as_utc(invite.expires_at),
                        "used_at": _as_utc(invite.used_at),
                        "revoked_at": _as_utc(invite.revoked_at),
                    },
                )
            )

    return documents


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy Chass! data from DATABASE_URL into the configured Firestore project."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the documents. Without this flag, only print the migration count.",
    )
    parser.add_argument(
        "--include-expired",
        action="store_true",
        help="Also copy expired games and their related records.",
    )
    args = parser.parse_args()

    documents = _load_documents(include_expired=args.include_expired)
    counts: dict[str, int] = defaultdict(int)
    for collection, _, _ in documents:
        counts[collection] += 1

    print("Documents ready:")
    for collection in (GAMES, PLAYERS, INVITES, MOVES):
        print(f"  {collection}: {counts[collection]}")

    if not args.apply:
        print("Dry run only. Re-run with --apply to write to Firestore.")
        return

    _commit_documents(get_firestore_client(), documents)
    print("Migration complete.")


if __name__ == "__main__":
    main()
