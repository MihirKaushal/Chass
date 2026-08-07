from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from backend.models.schemas import CreateGameRequest, JoinGameRequest
from backend.repositories import ConcurrentUpdateError, MoveAudit
from backend.repositories.firestore_repository import (
    GAMES,
    INVITES,
    MOVES,
    PLAYERS,
    FirestoreGameRepository,
)
from backend.rules import RuleEngine
from backend.services.game_service import GameService


class FakeSnapshot:
    def __init__(self, reference, data):
        self.reference = reference
        self.id = reference.id
        self._data = deepcopy(data)
        self.exists = data is not None

    def to_dict(self):
        return deepcopy(self._data) if self.exists else None


class FakeDocumentReference:
    def __init__(self, client, collection_name, document_id):
        self.client = client
        self.collection_name = collection_name
        self.id = document_id

    def get(self, transaction=None):
        if transaction is not None:
            return transaction.read(self)
        return self.client.snapshot(self)

    def update(self, values):
        self.client.apply("update", self, values)

    def delete(self):
        self.client.apply("delete", self, None)


class FakeQuery:
    def __init__(self, client, collection_name, filters=None, maximum=None):
        self.client = client
        self.collection_name = collection_name
        self.filters = filters or []
        self.maximum = maximum

    def where(self, *, filter):
        return FakeQuery(
            self.client,
            self.collection_name,
            [*self.filters, filter],
            self.maximum,
        )

    def limit(self, maximum):
        return FakeQuery(
            self.client,
            self.collection_name,
            self.filters,
            maximum,
        )

    @staticmethod
    def _matches(data, field_filter):
        current = data.get(field_filter.field_path)
        if field_filter.op_string == "==":
            return current == field_filter.value
        if field_filter.op_string == "<=":
            return current is not None and current <= field_filter.value
        raise AssertionError(f"Unsupported fake query operator: {field_filter.op_string}")

    def stream(self):
        snapshots = []
        for document_id, data in self.client.documents[self.collection_name].items():
            if all(self._matches(data, item) for item in self.filters):
                reference = FakeDocumentReference(
                    self.client,
                    self.collection_name,
                    document_id,
                )
                snapshots.append(FakeSnapshot(reference, data))
        return iter(snapshots[: self.maximum])


class FakeCollection(FakeQuery):
    def __init__(self, client, collection_name):
        super().__init__(client, collection_name)

    def document(self, document_id):
        return FakeDocumentReference(self.client, self.collection_name, document_id)


class FakeWriteGroup:
    def __init__(self, client):
        self.client = client
        self.operations = []

    def set(self, reference, values):
        self.operations.append(("set", reference, deepcopy(values)))

    def update(self, reference, values):
        self.operations.append(("update", reference, deepcopy(values)))

    def delete(self, reference):
        self.operations.append(("delete", reference, None))

    def commit(self):
        for operation, reference, values in self.operations:
            self.client.apply(operation, reference, values)
        self.operations.clear()


class FakeTransaction(FakeWriteGroup):
    def __init__(self, client):
        super().__init__(client)
        self.write_started = False

    def read(self, reference):
        if self.write_started:
            raise AssertionError("Firestore transactions must complete reads before writes")
        return self.client.snapshot(reference)

    def set(self, reference, values):
        self.write_started = True
        super().set(reference, values)

    def update(self, reference, values):
        self.write_started = True
        super().update(reference, values)


class FakeFirestoreClient:
    def __init__(self):
        self.documents = defaultdict(dict)

    def collection(self, collection_name):
        return FakeCollection(self, collection_name)

    def batch(self):
        return FakeWriteGroup(self)

    def transaction(self):
        return FakeTransaction(self)

    def snapshot(self, reference):
        data = self.documents[reference.collection_name].get(reference.id)
        return FakeSnapshot(reference, data)

    def apply(self, operation, reference, values):
        collection = self.documents[reference.collection_name]
        if operation == "set":
            collection[reference.id] = deepcopy(values)
        elif operation == "update":
            if reference.id not in collection:
                raise AssertionError("Cannot update a missing fake document")
            collection[reference.id].update(deepcopy(values))
        elif operation == "delete":
            collection.pop(reference.id, None)


def fake_transactional(function):
    def execute(transaction, *args, **kwargs):
        result = function(transaction, *args, **kwargs)
        transaction.commit()
        return result

    return execute


@pytest.fixture
def firestore_service(monkeypatch):
    monkeypatch.setenv("TOKEN_SECRET", "firestore-repository-test-secret")
    monkeypatch.setattr(
        "backend.repositories.firestore_repository.firestore.transactional",
        fake_transactional,
    )
    client = FakeFirestoreClient()
    repository = FirestoreGameRepository(client)
    return GameService(RuleEngine(), repository), repository, client


def test_firestore_invites_are_transactional_and_replaceable(firestore_service):
    service, _, client = firestore_service
    created = service.create_game(CreateGameRequest(mode="online"))

    replacement = service.replace_invite(created.game.id, created.playerToken)
    with pytest.raises(HTTPException, match="replaced") as old_invite:
        service.join_game(JoinGameRequest(inviteToken=created.inviteToken))
    assert old_invite.value.status_code == 409

    joined = service.join_game(JoinGameRequest(inviteToken=replacement.inviteToken))
    assert joined.playerColor == "black"
    assert joined.game.ready is True
    assert len(client.documents[PLAYERS]) == 2

    with pytest.raises(HTTPException, match="already been used"):
        service.join_game(JoinGameRequest(inviteToken=replacement.inviteToken))


def test_firestore_inactive_invite_cannot_revive_game(firestore_service):
    service, _, client = firestore_service
    created = service.create_game(CreateGameRequest(mode="online"))
    now = datetime.now(timezone.utc)
    client.documents[GAMES][created.game.id].update(
        {
            "updated_at": now - timedelta(hours=25),
            "expires_at": now + timedelta(days=30),
        }
    )

    with pytest.raises(HTTPException, match="inactivity") as expired:
        service.join_game(JoinGameRequest(inviteToken=created.inviteToken))

    assert expired.value.status_code == 409
    assert len(client.documents[PLAYERS]) == 1


def test_firestore_versions_and_move_audits_are_atomic(firestore_service):
    service, repository, client = firestore_service
    created = service.create_game(CreateGameRequest(mode="local"))
    record = repository.get_game(created.game.id)
    assert record is not None

    audit = MoveAudit(
        move_number=1,
        player_color="white",
        piece_type="pawn",
        from_row=6,
        from_col=4,
        to_row=4,
        to_col=4,
        explanation="Pawn moved.",
    )
    next_expiration = datetime.now(timezone.utc) + timedelta(hours=24)
    saved = repository.save_game(
        record.state,
        expected_version=1,
        audit=audit,
        expires_at=next_expiration,
    )
    assert saved.version == 2
    assert saved.expires_at == next_expiration
    assert f"{created.game.id}_2" in client.documents[MOVES]

    with pytest.raises(ConcurrentUpdateError):
        repository.save_game(record.state, expected_version=1)


def test_firestore_inactivity_removes_related_documents(firestore_service):
    service, repository, client = firestore_service
    created = service.create_game(CreateGameRequest(mode="online"))
    game_id = created.game.id
    now = datetime.now(timezone.utc)

    # Legacy games may still have a future creation-based deadline; activity wins.
    client.documents[GAMES][game_id]["updated_at"] = now - timedelta(hours=25)
    client.documents[GAMES][game_id]["expires_at"] = now + timedelta(days=30)
    client.documents[MOVES][f"{game_id}_2"] = {
        "game_id": game_id,
        "game_version": 2,
    }
    deleted = repository.delete_inactive_games(now - timedelta(hours=24), now)

    assert deleted == 1
    assert game_id not in client.documents[GAMES]
    for collection_name in (PLAYERS, INVITES, MOVES):
        assert all(
            document.get("game_id") != game_id
            for document in client.documents[collection_name].values()
        )


def test_firestore_cleanup_resumes_a_pending_deletion(firestore_service):
    service, repository, client = firestore_service
    created = service.create_game(CreateGameRequest(mode="online"))
    game_id = created.game.id
    now = datetime.now(timezone.utc)

    client.documents[GAMES][game_id].update(
        {
            "deletion_pending": True,
            "updated_at": now - timedelta(hours=25),
        }
    )

    assert repository.delete_inactive_games(now - timedelta(hours=24), now) == 1
    assert game_id not in client.documents[GAMES]
