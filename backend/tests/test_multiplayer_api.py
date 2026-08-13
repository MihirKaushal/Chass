from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from backend.db import GameInviteRow, GamePlayerRow, GameRow, MoveRow, session_scope


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_online_game(client) -> dict:
    response = client.post(
        "/game/create",
        json={
            "mode": "online",
            "boardRows": 8,
            "boardCols": 8,
            "rules": [],
            "customPieces": [],
        },
    )
    assert response.status_code == 200
    return response.json()


def test_local_game_remains_token_free(client):
    created = client.post("/game/create", json={"mode": "local"})

    assert created.status_code == 200
    session = created.json()
    game = session["game"]
    assert session["role"] == "local"
    assert session["playerToken"] is None
    assert game["mode"] == "local"
    assert game["ready"] is True
    assert game["version"] == 1

    moved = client.post(
        f"/game/{game['id']}/move",
        json={"fromRow": 6, "fromCol": 4, "toRow": 4, "toCol": 4},
    )
    assert moved.status_code == 200
    assert moved.json()["version"] == 2
    assert moved.json()["currentPlayer"] == "black"

    loaded = client.get(f"/game/{game['id']}")
    assert loaded.status_code == 200
    assert loaded.json()["version"] == 2


def test_game_creation_does_not_wait_for_retention_cleanup(client, monkeypatch):
    from backend.routes.game import game_service

    def unexpected_cleanup(*_args, **_kwargs):
        raise AssertionError("game creation must not run global cleanup")

    monkeypatch.setattr(game_service, "cleanup_inactive_games", unexpected_cleanup)
    created = client.post("/game/create", json={"mode": "local"})
    assert created.status_code == 200


def test_same_device_restart_requires_both_colors(client):
    game = client.post("/game/create", json={"mode": "local"}).json()["game"]
    moved = client.post(
        f"/game/{game['id']}/move",
        json={
            "fromRow": 6,
            "fromCol": 4,
            "toRow": 4,
            "toCol": 4,
            "expectedVersion": game["version"],
        },
    ).json()

    direct_reset = client.post(
        f"/game/{game['id']}/reset",
        json={"expectedVersion": moved["version"]},
    )
    assert direct_reset.status_code == 409

    requested = client.post(
        f"/game/{game['id']}/rematch",
        json={
            "action": "request",
            "color": "white",
            "expectedVersion": moved["version"],
        },
    )
    assert requested.status_code == 200
    pending = requested.json()
    assert pending["history"]
    assert pending["rematch"]["approvals"] == {"white": True, "black": False}

    accepted = client.post(
        f"/game/{game['id']}/rematch",
        json={
            "action": "accept",
            "color": "black",
            "expectedVersion": pending["version"],
        },
    )
    assert accepted.status_code == 200
    restarted = accepted.json()
    assert restarted["history"] == []
    assert restarted["currentPlayer"] == "white"
    assert restarted["board"][6][4]["type"] == "pawn"
    assert restarted["rematch"]["status"] == "idle"


def test_either_online_player_can_request_restart_and_other_must_approve(client):
    created = create_online_game(client)
    joined = client.post(
        "/game/join",
        json={"inviteToken": created["inviteToken"]},
    ).json()
    game_id = created["game"]["id"]

    requested = client.post(
        f"/game/{game_id}/rematch",
        headers=auth(joined["playerToken"]),
        json={
            "action": "request",
            "expectedVersion": joined["game"]["version"],
        },
    )
    assert requested.status_code == 200
    pending = requested.json()
    assert pending["rematch"]["requestedBy"] == "black"
    assert pending["rematch"]["approvals"] == {"white": False, "black": True}

    accepted = client.post(
        f"/game/{game_id}/rematch",
        headers=auth(created["playerToken"]),
        json={"action": "accept", "expectedVersion": pending["version"]},
    )
    assert accepted.status_code == 200
    restarted = accepted.json()
    assert restarted["history"] == []
    assert restarted["rematch"]["status"] == "idle"


def test_online_invite_and_seat_authorization(client):
    created = create_online_game(client)
    game = created["game"]
    host_token = created["playerToken"]

    assert created["playerColor"] == "white"
    assert created["role"] == "host"
    assert created["inviteCode"] == created["inviteToken"]
    assert re.fullmatch(r"[2-9A-HJ-NP-Z]{8}", created["inviteCode"])
    assert created["inviteUrl"].endswith(f"/join/{created['inviteCode']}")
    assert created["inviteToken"] not in str(game)
    assert game["ready"] is False
    assert game["players"] == {"white": "joined", "black": "open"}

    assert client.get(f"/game/{game['id']}").status_code == 401

    waiting_move = client.post(
        f"/game/{game['id']}/move",
        headers=auth(host_token),
        json={
            "fromRow": 6,
            "fromCol": 4,
            "toRow": 4,
            "toCol": 4,
            "expectedVersion": 1,
        },
    )
    assert waiting_move.status_code == 409

    display_code = f"{created['inviteCode'][:4]}-{created['inviteCode'][4:]}".lower()
    joined = client.post("/game/join", json={"inviteCode": display_code})
    assert joined.status_code == 200
    black_session = joined.json()
    assert black_session["playerColor"] == "black"
    assert black_session["game"]["ready"] is True

    reused = client.post(
        "/game/join",
        json={"inviteToken": created["inviteToken"]},
    )
    assert reused.status_code == 409

    black_moves_white = client.post(
        f"/game/{game['id']}/move",
        headers=auth(black_session["playerToken"]),
        json={
            "fromRow": 6,
            "fromCol": 4,
            "toRow": 4,
            "toCol": 4,
            "expectedVersion": 1,
        },
    )
    assert black_moves_white.status_code == 403

    white_move = client.post(
        f"/game/{game['id']}/move",
        headers=auth(host_token),
        json={
            "fromRow": 6,
            "fromCol": 4,
            "toRow": 4,
            "toCol": 4,
            "expectedVersion": 1,
        },
    )
    assert white_move.status_code == 200
    assert white_move.json()["version"] == 2

    stale_black_move = client.post(
        f"/game/{game['id']}/move",
        headers=auth(black_session["playerToken"]),
        json={
            "fromRow": 1,
            "fromCol": 4,
            "toRow": 3,
            "toCol": 4,
            "expectedVersion": 1,
        },
    )
    assert stale_black_move.status_code == 409

    black_move = client.post(
        f"/game/{game['id']}/move",
        headers=auth(black_session["playerToken"]),
        json={
            "fromRow": 1,
            "fromCol": 4,
            "toRow": 3,
            "toCol": 4,
            "expectedVersion": 2,
        },
    )
    assert black_move.status_code == 200
    assert black_move.json()["version"] == 3
    assert black_move.json()["currentPlayer"] == "white"


def test_only_host_can_customize_online_game(client):
    created = create_online_game(client)
    game_id = created["game"]["id"]
    host_token = created["playerToken"]
    joined = client.post(
        "/game/join",
        json={"inviteToken": created["inviteToken"]},
    ).json()

    guest_change = client.post(
        f"/game/{game_id}/rules",
        headers=auth(joined["playerToken"]),
        json={
            "expectedVersion": 1,
            "rules": [{"id": "score_target_win", "enabled": True}],
        },
    )
    assert guest_change.status_code == 403

    host_change = client.post(
        f"/game/{game_id}/rules",
        headers=auth(host_token),
        json={
            "expectedVersion": 1,
            "rules": [
                {
                    "id": "score_target_win",
                    "enabled": True,
                    "params": {"targetScore": 21},
                }
            ],
        },
    )
    assert host_change.status_code == 200
    assert host_change.json()["version"] == 2
    target_rule = next(
        rule for rule in host_change.json()["rules"] if rule["id"] == "score_target_win"
    )
    assert target_rule["enabled"] is True
    assert target_rule["params"]["targetScore"] == 21

    full_game_invite = client.post(
        f"/game/{game_id}/invite",
        headers=auth(host_token),
    )
    assert full_game_invite.status_code == 409


def test_host_can_replace_unused_invite(client):
    created = create_online_game(client)
    game_id = created["game"]["id"]

    replacement = client.post(
        f"/game/{game_id}/invite",
        headers=auth(created["playerToken"]),
    )
    assert replacement.status_code == 200
    next_invite = replacement.json()
    assert next_invite["inviteToken"] != created["inviteToken"]
    assert next_invite["inviteCode"] == next_invite["inviteToken"]
    assert re.fullmatch(r"[2-9A-HJ-NP-Z]{8}", next_invite["inviteCode"])
    assert "/join/" in next_invite["inviteUrl"]

    old_join = client.post("/game/join", json={"inviteToken": created["inviteToken"]})
    assert old_join.status_code == 409
    assert "replaced" in old_join.json()["detail"].lower()

    new_join = client.post("/game/join", json={"inviteToken": next_invite["inviteToken"]})
    assert new_join.status_code == 200


def test_inactive_invite_cannot_revive_game(client):
    created = create_online_game(client)
    game_id = created["game"]["id"]
    now = datetime.now(timezone.utc)

    with session_scope() as session:
        game = session.get(GameRow, game_id)
        assert game is not None
        game.updated_at = now - timedelta(hours=25)
        game.expires_at = now + timedelta(days=30)
        session.commit()

    joined = client.post(
        "/game/join",
        json={"inviteToken": created["inviteToken"]},
    )
    assert joined.status_code == 409
    assert "inactivity" in joined.json()["detail"].lower()


def test_websocket_authenticates_before_joining_room(client):
    created = create_online_game(client)
    game_id = created["game"]["id"]

    with client.websocket_connect(f"/game/ws/{game_id}") as websocket:
        websocket.send_json(
            {
                "type": "authenticate",
                "token": created["playerToken"],
            }
        )
        initial = websocket.receive_json()
        assert initial["type"] == "game_state"
        assert initial["game"]["id"] == game_id
        assert initial["game"]["version"] == 1

        presence = websocket.receive_json()
        assert presence["type"] == "presence"
        assert presence["connected"]["white"] is True


def test_successful_move_refreshes_idle_expiration(client):
    created = client.post("/game/create", json={"mode": "local"}).json()
    game_id = created["game"]["id"]
    now = datetime.now(timezone.utc)

    with session_scope() as session:
        game = session.get(GameRow, game_id)
        assert game is not None
        game.expires_at = now + timedelta(minutes=5)
        game.updated_at = now
        session.commit()

    moved = client.post(
        f"/game/{game_id}/move",
        json={"fromRow": 6, "fromCol": 4, "toRow": 4, "toCol": 4},
    )
    assert moved.status_code == 200

    with session_scope() as session:
        game = session.get(GameRow, game_id)
        assert game is not None
        assert as_utc(game.expires_at) >= now + timedelta(hours=23, minutes=59)


def test_inactive_game_access_deletes_all_associated_data(client):
    created = create_online_game(client)
    game_id = created["game"]["id"]
    joined = client.post(
        "/game/join",
        json={"inviteToken": created["inviteToken"]},
    ).json()

    moved = client.post(
        f"/game/{game_id}/move",
        headers=auth(created["playerToken"]),
        json={
            "fromRow": 6,
            "fromCol": 4,
            "toRow": 4,
            "toCol": 4,
            "expectedVersion": 1,
        },
    )
    assert moved.status_code == 200

    now = datetime.now(timezone.utc)
    with session_scope() as session:
        game = session.get(GameRow, game_id)
        assert game is not None
        game.updated_at = now - timedelta(hours=25)
        game.expires_at = now + timedelta(days=30)
        session.commit()

    expired = client.get(
        f"/game/{game_id}",
        headers=auth(joined["playerToken"]),
    )
    assert expired.status_code == 410

    with session_scope() as session:
        assert session.get(GameRow, game_id) is None
        for model in (GamePlayerRow, GameInviteRow, MoveRow):
            count = session.scalar(
                select(func.count()).select_from(model).where(model.game_id == game_id)
            )
            assert count == 0
