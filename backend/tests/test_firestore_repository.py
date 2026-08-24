from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from google.api_core.exceptions import FailedPrecondition

from backend.models import GameState, MoveRecord
from backend.models.schemas import CreateGameRequest, JoinGameRequest, MoveRequest
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
    def __init__(self, reference, data, update_time=None):
        self.reference = reference
        self.id = reference.id
        self._data = deepcopy(data)
        self.exists = data is not None
        self.update_time = update_time

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

    def update(self, values, option=None):
        self.client.validate_option(self, option)
        self.client.apply("update", self, values)

    def delete(self):
        self.client.apply("delete", self, None)


class FakeQuery:
    def __init__(
        self,
        client,
        collection_name,
        filters=None,
        maximum=None,
        orders=None,
    ):
        self.client = client
        self.collection_name = collection_name
        self.filters = filters or []
        self.maximum = maximum
        self.orders = orders or []

    def where(self, *, filter):
        return FakeQuery(
            self.client,
            self.collection_name,
            [*self.filters, filter],
            self.maximum,
            self.orders,
        )

    def limit(self, maximum):
        return FakeQuery(
            self.client,
            self.collection_name,
            self.filters,
            maximum,
            self.orders,
        )

    def order_by(self, field_path, direction=None):
        return FakeQuery(
            self.client,
            self.collection_name,
            self.filters,
            self.maximum,
            [*self.orders, (field_path, direction)],
        )

    @staticmethod
    def _matches(data, field_filter):
        current = data.get(field_filter.field_path)
        if field_filter.op_string == "==":
            return current == field_filter.value
        if field_filter.op_string == "<=":
            return current is not None and current <= field_filter.value
        if field_filter.op_string == "<":
            return current is not None and current < field_filter.value
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
                snapshots.append(
                    FakeSnapshot(
                        reference,
                        data,
                        self.client.revisions[self.collection_name].get(document_id),
                    )
                )
        for field_path, direction in reversed(self.orders):
            descending = "DESCENDING" in str(direction).upper()
            snapshots.sort(
                key=lambda snapshot: (snapshot.to_dict() or {}).get(field_path),
                reverse=descending,
            )
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
        self.operations.append(("set", reference, deepcopy(values), None))

    def update(self, reference, values, option=None):
        self.operations.append(("update", reference, deepcopy(values), option))

    def delete(self, reference):
        self.operations.append(("delete", reference, None, None))

    def commit(self):
        for _, reference, _, option in self.operations:
            self.client.validate_option(reference, option)
        results = []
        for operation, reference, values, _ in self.operations:
            results.append(FakeWriteResult(self.client.apply(operation, reference, values)))
        self.operations.clear()
        return results


class FakeWriteResult:
    def __init__(self, update_time):
        self.update_time = update_time


class FakeTransaction(FakeWriteGroup):
    def __init__(self, client):
        super().__init__(client)
        self.write_started = False

    def read(self, reference):
        if self.write_started:
            raise AssertionError("Firestore transactions must complete reads before writes")
        self.client.transaction_reads += 1
        return self.client.snapshot(reference)

    def set(self, reference, values):
        self.write_started = True
        super().set(reference, values)

    def update(self, reference, values, option=None):
        self.write_started = True
        super().update(reference, values, option=option)


class FakeFirestoreClient:
    def __init__(self):
        self.documents = defaultdict(dict)
        self.revisions = defaultdict(dict)
        self.reads = defaultdict(int)
        self.revision_counter = 0
        self.transaction_reads = 0

    def collection(self, collection_name):
        return FakeCollection(self, collection_name)

    def batch(self):
        return FakeWriteGroup(self)

    def transaction(self):
        return FakeTransaction(self)

    def snapshot(self, reference):
        self.reads[reference.collection_name] += 1
        data = self.documents[reference.collection_name].get(reference.id)
        return FakeSnapshot(
            reference,
            data,
            self.revisions[reference.collection_name].get(reference.id),
        )

    def validate_option(self, reference, option):
        if option is None:
            return
        expected = getattr(option, "_last_update_time", None)
        current = self.revisions[reference.collection_name].get(reference.id)
        if current != expected:
            raise FailedPrecondition("Fake document revision changed")

    def next_revision(self):
        self.revision_counter += 1
        return datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(
            microseconds=self.revision_counter
        )

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
            self.revisions[reference.collection_name].pop(reference.id, None)
            return None
        revision = self.next_revision()
        self.revisions[reference.collection_name][reference.id] = revision
        return revision


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


def test_firestore_repository_resolves_the_shared_client_lazily(monkeypatch):
    clients = [FakeFirestoreClient(), FakeFirestoreClient()]
    active_client = [clients[0]]
    monkeypatch.setattr(
        "backend.repositories.firestore_repository.get_firestore_client",
        lambda: active_client[0],
    )
    repository = FirestoreGameRepository()

    assert repository.client is clients[0]
    active_client[0] = clients[1]
    assert repository.client is clients[1]


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
    transaction_reads = client.transaction_reads
    saved = repository.save_game(
        record.state,
        expected_version=1,
        audit=audit,
        expires_at=next_expiration,
        expected_revision=record.persistence_revision,
        current_record=record,
    )
    assert saved.version == 2
    assert saved.expires_at == next_expiration
    assert saved.persistence_revision != record.persistence_revision
    assert client.transaction_reads == transaction_reads
    assert f"{created.game.id}_2" in client.documents[MOVES]

    with pytest.raises(ConcurrentUpdateError):
        repository.save_game(
            record.state,
            expected_version=1,
            expected_revision=record.persistence_revision,
            current_record=record,
        )


def test_firestore_online_move_reuses_authorized_player_and_revision(firestore_service):
    service, repository, client = firestore_service
    created = service.create_game(CreateGameRequest(mode="online"))
    service.join_game(JoinGameRequest(inviteToken=created.inviteToken))
    record = repository.get_game(created.game.id)
    assert record is not None

    client.reads.clear()
    transaction_reads = client.transaction_reads
    saved, _, viewer_color = service.move_piece(
        created.game.id,
        MoveRequest(
            fromRow=6,
            fromCol=4,
            toRow=4,
            toCol=4,
            expectedVersion=record.version,
        ),
        created.playerToken,
    )

    assert saved.version == record.version + 1
    assert viewer_color == "white"
    assert client.reads[PLAYERS] == 1
    assert client.transaction_reads == transaction_reads


def test_firestore_pages_complete_history_outside_game_document(firestore_service):
    service, repository, client = firestore_service
    created = service.create_game(CreateGameRequest(mode="local"))
    record = repository.get_game(created.game.id)
    assert record is not None
    assert record.history_paged is True

    for move_number in range(1, 126):
        state = record.state.clone()
        move_record = MoveRecord(
            move_number=state.next_move_number(),
            player="white" if move_number % 2 else "black",
            piece="rook",
            from_row=7 if move_number % 2 else 0,
            from_col=0,
            to_row=6 if move_number % 2 else 1,
            to_col=0,
            explanation=f"Recorded move {move_number}.",
            action_type="ability" if move_number == 1 else "move",
        )
        state.history.append(move_record)
        record = repository.save_game(
            state,
            expected_version=record.version,
            audit=MoveAudit.from_record(move_record),
        )

    stored = GameState.model_validate_json(
        client.documents[GAMES][created.game.id]["state_json"]
    )
    assert len(stored.history) == 100
    assert stored.history[0].move_number == 26
    assert stored.history[-1].move_number == 125
    assert len(client.documents[MOVES]) == 125
    assert len(client.documents[GAMES][created.game.id]["state_json"].encode()) < 100_000

    newest = repository.get_history_page(created.game.id, 0, limit=25)
    assert [item.move_number for item in newest.records] == list(range(101, 126))
    assert newest.has_more is True
    assert newest.next_before == 101

    middle = repository.get_history_page(
        created.game.id,
        0,
        before_move_number=newest.next_before,
        limit=25,
    )
    assert [item.move_number for item in middle.records] == list(range(76, 101))
    assert middle.has_more is True

    oldest = repository.get_history_page(
        created.game.id,
        0,
        before_move_number=26,
        limit=25,
    )
    assert [item.move_number for item in oldest.records] == list(range(1, 26))
    assert oldest.records[0].action_type == "ability"
    assert oldest.has_more is False
    assert oldest.next_before is None

    api_page = service.get_history_page(
        created.game.id,
        before_move_number=26,
        limit=25,
    )
    assert api_page.pagination.totalMoves == 125
    assert api_page.pagination.epoch == 0
    assert api_page.history[0].moveNumber == 1


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
