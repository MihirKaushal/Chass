from __future__ import annotations

from backend.models import MoveRecord
from backend.routes.game import game_service


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def synthetic_history(count: int) -> list[MoveRecord]:
    return [
        MoveRecord(
            move_number=move_number,
            player="white" if move_number % 2 else "black",
            piece="knight",
            from_row=7 if move_number % 2 else 0,
            from_col=1,
            to_row=5 if move_number % 2 else 2,
            to_col=0,
            explanation=f"Synthetic move {move_number}.",
        )
        for move_number in range(1, count + 1)
    ]


def test_game_response_and_history_endpoint_page_long_matches(client):
    created = client.post("/game/create", json={"mode": "local"}).json()["game"]
    record = game_service.repository.get_game(created["id"])
    assert record is not None
    record.state.history = synthetic_history(105)
    game_service.repository.save_game(record.state, record.version)

    loaded = client.get(f"/game/{created['id']}")
    assert loaded.status_code == 200
    game = loaded.json()
    assert len(game["history"]) == 100
    assert game["history"][0]["moveNumber"] == 6
    assert game["historyPagination"] == {
        "epoch": 0,
        "totalMoves": 105,
        "hasMore": True,
        "nextBefore": 6,
    }

    earlier = client.get(
        f"/game/{created['id']}/history",
        params={"before": 6, "limit": 10},
    )
    assert earlier.status_code == 200
    page = earlier.json()
    assert [item["moveNumber"] for item in page["history"]] == [1, 2, 3, 4, 5]
    assert page["pagination"] == {
        "epoch": 0,
        "totalMoves": 105,
        "hasMore": False,
        "nextBefore": None,
    }


def test_rematch_starts_a_new_history_epoch(client):
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
    requested = client.post(
        f"/game/{game['id']}/rematch",
        json={
            "action": "request",
            "color": "white",
            "expectedVersion": moved["version"],
        },
    ).json()
    restarted = client.post(
        f"/game/{game['id']}/rematch",
        json={
            "action": "accept",
            "color": "black",
            "expectedVersion": requested["version"],
        },
    ).json()

    assert restarted["history"] == []
    assert restarted["historyPagination"] == {
        "epoch": 1,
        "totalMoves": 0,
        "hasMore": False,
        "nextBefore": None,
    }


def test_online_history_uses_game_seat_authorization(client):
    created = client.post("/game/create", json={"mode": "online"}).json()
    client.post("/game/join", json={"inviteToken": created["inviteToken"]})

    anonymous = client.get(f"/game/{created['game']['id']}/history")
    assert anonymous.status_code == 401

    authorized = client.get(
        f"/game/{created['game']['id']}/history",
        headers=auth(created["playerToken"]),
    )
    assert authorized.status_code == 200
    assert authorized.json()["history"] == []
