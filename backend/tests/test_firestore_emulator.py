from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from google.cloud.firestore_v1.base_query import FieldFilter

from backend.models.schemas import CreateGameRequest, JoinGameRequest
from backend.repositories import MoveAudit
from backend.repositories.firestore_repository import (
    GAMES,
    INVITES,
    MOVES,
    PLAYERS,
    FirestoreGameRepository,
)
from backend.rules import RuleEngine
from backend.services.game_service import GameService

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Firestore emulator is not running",
)


def test_firestore_emulator_game_lifecycle(monkeypatch):
    monkeypatch.setenv("TOKEN_SECRET", "firestore-emulator-test-secret")
    repository = FirestoreGameRepository()
    service = GameService(RuleEngine(), repository)

    created = service.create_game(CreateGameRequest(mode="online"))
    joined = service.join_game(JoinGameRequest(inviteToken=created.inviteToken))
    assert joined.game.ready is True

    record = repository.get_game(created.game.id)
    assert record is not None
    saved = repository.save_game(
        record.state,
        expected_version=1,
        audit=MoveAudit(
            move_number=1,
            player_color="white",
            piece_type="pawn",
            from_row=6,
            from_col=4,
            to_row=4,
            to_col=4,
            explanation="Pawn moved.",
        ),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    assert saved.version == 2

    now = datetime.now(timezone.utc)
    repository.client.collection(GAMES).document(created.game.id).update(
        {
            "updated_at": now - timedelta(hours=25),
            "expires_at": now + timedelta(days=30),
        }
    )
    assert repository.delete_inactive_games(now - timedelta(hours=24), now) == 1
    assert repository.get_game(created.game.id) is None

    for collection_name in (PLAYERS, INVITES, MOVES):
        related = list(
            repository.client.collection(collection_name)
            .where(filter=FieldFilter("game_id", "==", created.game.id))
            .stream()
        )
        assert related == []
