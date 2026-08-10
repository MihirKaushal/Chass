from __future__ import annotations

import asyncio

from backend.models import Board, GambitState, GameState, Move
from backend.models.schemas import CreateGameRequest
from backend.realtime import GameSocketManager, SocketIdentity
from backend.rules import RuleEngine
from backend.rules.gambit_rules import create_piece
from backend.services.game_service import build_default_piece_definitions

STANDARD_DEPLOYMENT = [
    "rook",
    "knight",
    "bishop",
    "queen",
    "king",
    "bishop",
    "knight",
    "rook",
]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def board_piece_count(game: dict) -> int:
    return sum(piece is not None for row in game["board"] for piece in row)


def deploy_standard_local(client, game_id: str, color: str, version: int) -> int:
    back_row = 7 if color == "white" else 0
    pawn_row = 6 if color == "white" else 1
    for col, piece_type in enumerate(STANDARD_DEPLOYMENT):
        response = client.post(
            f"/game/{game_id}/gambit/deployment",
            json={
                "action": "place",
                "row": back_row,
                "col": col,
                "pieceType": piece_type,
                "expectedVersion": version,
            },
        )
        assert response.status_code == 200
        version = response.json()["version"]

    for col in range(8):
        response = client.post(
            f"/game/{game_id}/gambit/deployment",
            json={
                "action": "place",
                "row": pawn_row,
                "col": col,
                "pieceType": "pawn",
                "expectedVersion": version,
            },
        )
        assert response.status_code == 200
        version = response.json()["version"]
    return version


def test_local_gambit_hides_armies_until_legal_reveal(client):
    created = client.post(
        "/game/create",
        json={"mode": "local", "variant": "gambit"},
    )
    assert created.status_code == 200
    game = created.json()["game"]
    game_id = game["id"]
    version = game["version"]

    assert game["variant"] == "gambit"
    assert game["phase"] == "deployment"
    assert game["gambit"]["editableColor"] == "white"
    assert board_piece_count(game) == 0

    version = deploy_standard_local(client, game_id, "white", version)
    white_ready = client.post(
        f"/game/{game_id}/gambit/ready",
        json={"expectedVersion": version},
    )
    assert white_ready.status_code == 200
    game = white_ready.json()
    version = game["version"]
    assert game["phase"] == "handoff"
    assert game["gambit"]["deploymentReady"] == {"white": True, "black": False}
    assert board_piece_count(game) == 0

    handoff = client.post(
        f"/game/{game_id}/gambit/handoff",
        json={"expectedVersion": version},
    )
    assert handoff.status_code == 200
    game = handoff.json()
    version = game["version"]
    assert game["phase"] == "deployment"
    assert game["gambit"]["editableColor"] == "black"
    assert board_piece_count(game) == 0

    version = deploy_standard_local(client, game_id, "black", version)
    black_ready = client.post(
        f"/game/{game_id}/gambit/ready",
        json={"expectedVersion": version},
    )
    assert black_ready.status_code == 200
    game = black_ready.json()

    assert game["phase"] == "play"
    assert game["currentPlayer"] == "white"
    assert board_piece_count(game) == 32
    assert game["gambit"]["setupSummary"] is None
    assert len(game["validMoves"]) == 20


def test_online_gambit_serialization_never_leaks_opponent_deployment(client):
    created = client.post(
        "/game/create",
        json={"mode": "online", "variant": "gambit"},
    ).json()
    host_token = created["playerToken"]
    game_id = created["game"]["id"]
    assert created["game"]["phase"] == "lobby"

    joined = client.post(
        "/game/join",
        json={"inviteToken": created["inviteToken"]},
    )
    assert joined.status_code == 200
    guest = joined.json()
    version = guest["game"]["version"]
    assert guest["game"]["phase"] == "deployment"

    white_piece = client.post(
        f"/game/{game_id}/gambit/deployment",
        headers=auth(host_token),
        json={
            "action": "place",
            "row": 7,
            "col": 4,
            "pieceType": "king",
            "expectedVersion": version,
        },
    )
    assert white_piece.status_code == 200
    version = white_piece.json()["version"]

    second_white_piece = client.post(
        f"/game/{game_id}/gambit/deployment",
        headers=auth(host_token),
        json={
            "action": "place",
            "row": 7,
            "col": 3,
            "pieceType": "queen",
            "expectedVersion": version,
        },
    )
    assert second_white_piece.status_code == 200
    version = second_white_piece.json()["version"]

    black_view = client.get(
        f"/game/{game_id}",
        headers=auth(guest["playerToken"]),
    ).json()
    assert board_piece_count(black_view) == 0
    assert black_view["version"] == guest["game"]["version"]
    assert black_view["gambit"]["viewerColor"] == "black"
    assert black_view["gambit"]["setupSummary"]["pieceCount"] == 0

    black_piece = client.post(
        f"/game/{game_id}/gambit/deployment",
        headers=auth(guest["playerToken"]),
        json={
            "action": "place",
            "row": 0,
            "col": 4,
            "pieceType": "king",
            "expectedVersion": version,
        },
    )
    assert black_piece.status_code == 200

    white_view = client.get(
        f"/game/{game_id}",
        headers=auth(host_token),
    ).json()
    assert white_view["version"] == version
    assert board_piece_count(white_view) == 2
    assert white_view["board"][7][4]["color"] == "white"
    assert "black" not in str(white_view["board"])

    latest_black_view = client.get(
        f"/game/{game_id}",
        headers=auth(guest["playerToken"]),
    ).json()
    assert board_piece_count(latest_black_view) == 1
    assert latest_black_view["board"][0][4]["color"] == "black"
    assert "white" not in str(latest_black_view["board"])


def test_hidden_deployment_broadcast_targets_only_the_editing_seat():
    class FakeSocket:
        def __init__(self) -> None:
            self.messages: list[dict] = []

        async def send_json(self, message: dict) -> None:
            self.messages.append(message)

    async def exercise() -> tuple[list[dict], list[dict]]:
        manager = GameSocketManager()
        white = FakeSocket()
        black = FakeSocket()
        await manager.connect(
            "private-game",
            white,
            SocketIdentity(color="white", role="host"),
            accept=False,
        )
        await manager.connect(
            "private-game",
            black,
            SocketIdentity(color="black", role="player"),
            accept=False,
        )
        await manager.broadcast_personalized(
            "private-game",
            "game_state",
            lambda identity: {"viewer": identity.color},
            identity_filter=lambda identity: identity.color == "white",
        )
        return white.messages, black.messages

    white_messages, black_messages = asyncio.run(exercise())
    assert white_messages == [{"type": "game_state", "viewer": "white"}]
    assert black_messages == []


def test_gambit_composition_rules_reject_invalid_armies(client):
    created = client.post(
        "/game/create",
        json={"mode": "local", "variant": "gambit"},
    ).json()["game"]
    game_id = created["id"]
    version = created["version"]

    for col in range(2):
        response = client.post(
            f"/game/{game_id}/gambit/deployment",
            json={
                "action": "place",
                "row": 7,
                "col": col,
                "pieceType": "queen",
                "expectedVersion": version,
            },
        )
        assert response.status_code == 200
        version = response.json()["version"]

    third_queen = client.post(
        f"/game/{game_id}/gambit/deployment",
        json={
            "action": "place",
            "row": 7,
            "col": 2,
            "pieceType": "queen",
            "expectedVersion": version,
        },
    )
    assert third_queen.status_code == 400
    assert "at most 2 queens" in third_queen.json()["detail"]

    incomplete = client.post(
        f"/game/{game_id}/gambit/ready",
        json={"expectedVersion": version},
    )
    assert incomplete.status_code == 400
    assert "exactly one King" in incomplete.json()["detail"]


def test_illegal_hidden_opening_returns_generic_handoff(client):
    game = client.post(
        "/game/create",
        json={"mode": "local", "variant": "gambit"},
    ).json()["game"]
    game_id = game["id"]
    version = game["version"]

    for row, col, piece_type in [(7, 4, "king"), (6, 4, "rook")]:
        response = client.post(
            f"/game/{game_id}/gambit/deployment",
            json={
                "action": "place",
                "row": row,
                "col": col,
                "pieceType": piece_type,
                "expectedVersion": version,
            },
        )
        assert response.status_code == 200
        version = response.json()["version"]

    response = client.post(
        f"/game/{game_id}/gambit/ready",
        json={"expectedVersion": version},
    )
    version = response.json()["version"]
    response = client.post(
        f"/game/{game_id}/gambit/handoff",
        json={"expectedVersion": version},
    )
    version = response.json()["version"]

    for row, col, piece_type in [(0, 4, "king"), (0, 0, "rook")]:
        response = client.post(
            f"/game/{game_id}/gambit/deployment",
            json={
                "action": "place",
                "row": row,
                "col": col,
                "pieceType": piece_type,
                "expectedVersion": version,
            },
        )
        assert response.status_code == 200
        version = response.json()["version"]

    response = client.post(
        f"/game/{game_id}/gambit/ready",
        json={"expectedVersion": version},
    )
    assert response.status_code == 200
    game = response.json()
    assert game["phase"] == "handoff"
    assert game["gambit"]["deploymentReady"] == {"white": False, "black": False}
    assert "hidden armies" in game["gambit"]["setupMessage"].lower()
    assert board_piece_count(game) == 0


def test_affinity_awards_one_point_and_reinforce_consumes_the_turn():
    engine = RuleEngine()
    definitions = build_default_piece_definitions()
    board = Board(rows=8, cols=8, grid=[[None for _ in range(8)] for _ in range(8)])
    state = GameState(
        id="gambit-rule-test",
        board=board,
        variant="gambit",
        phase="play",
        gambit=GambitState(),
        piece_definitions=definitions,
        rules=engine.default_rule_settings(),
    )

    state.board.grid[7][4] = create_piece(state, "king", "white")
    state.board.grid[0][7] = create_piece(state, "king", "black")
    state.board.grid[4][4] = create_piece(state, "rook", "white")
    state.board.grid[3][3] = create_piece(state, "bishop", "white")

    state, _ = engine.apply_move(
        state,
        Move(fromRow=7, fromCol=4, toRow=6, toCol=4),
    )
    assert state.gambit is not None
    assert state.gambit.affinity_primed["white"] is True

    state, _ = engine.apply_move(
        state,
        Move(fromRow=0, fromCol=7, toRow=1, toCol=7),
    )
    assert state.current_player == "white"
    assert state.gambit.command_points["white"] == 1

    state, explanation = engine.apply_gambit_power(
        state,
        "white",
        power="reinforce",
        row=7,
        col=0,
        evolve_to=None,
    )
    assert state.current_player == "black"
    assert state.gambit.command_points["white"] == 0
    assert state.gambit.power_usage["white"]["reinforce"] == 1
    assert state.board.grid[7][0].type == "pawn"
    assert state.board.grid[7][0].has_moved is True
    assert state.history[-1].action_type == "reinforce"
    assert "used Reinforce" in explanation


def make_gambit_play_state() -> tuple[RuleEngine, GameState]:
    engine = RuleEngine()
    state = GameState(
        id="gambit-power-test",
        board=Board(rows=8, cols=8, grid=[[None for _ in range(8)] for _ in range(8)]),
        variant="gambit",
        phase="play",
        gambit=GambitState(),
        piece_definitions=build_default_piece_definitions(),
        rules=engine.default_rule_settings(),
    )
    state.board.grid[7][4] = create_piece(state, "king", "white")
    state.board.grid[0][7] = create_piece(state, "king", "black")
    return engine, state


def test_evolve_and_stronghold_apply_through_command_rules():
    engine, evolve_state = make_gambit_play_state()
    assert evolve_state.gambit is not None
    evolve_state.board.grid[4][0] = create_piece(evolve_state, "pawn", "white")
    evolve_state.gambit.command_points["white"] = 2

    evolved, _ = engine.apply_gambit_power(
        evolve_state,
        "white",
        power="evolve",
        row=4,
        col=0,
        evolve_to="bishop",
    )
    assert evolved.board.grid[4][0].type == "bishop"
    assert evolved.gambit.command_points["white"] == 0
    assert evolved.gambit.power_usage["white"]["evolve"] == 1

    engine, stronghold_state = make_gambit_play_state()
    assert stronghold_state.gambit is not None
    stronghold_state.gambit.command_points["white"] = 3
    fortified, _ = engine.apply_gambit_power(
        stronghold_state,
        "white",
        power="stronghold",
        row=5,
        col=0,
        evolve_to=None,
    )
    assert fortified.board.grid[5][0].type == "rook"
    assert fortified.board.grid[5][0].has_moved is True
    assert fortified.gambit.command_points["white"] == 0
    assert fortified.gambit.power_usage["white"]["stronghold"] == 1


def test_command_power_can_resolve_check_and_prevent_false_checkmate():
    engine, state = make_gambit_play_state()
    assert state.gambit is not None
    state.board.grid[0][4] = create_piece(state, "rook", "black")
    state.gambit.command_points["white"] = 1
    assert engine.is_king_in_check(state, "white") is True

    engine.evaluate_state(state)
    assert state.game_status == "check"
    assert any(
        target == {"row": 6, "col": 4}
        for target in engine.gambit.legal_power_targets(state, "white", engine)["reinforce"]
    )

    rescued, _ = engine.apply_gambit_power(
        state,
        "white",
        power="reinforce",
        row=6,
        col=4,
        evolve_to=None,
    )
    assert engine.is_king_in_check(rescued, "white") is False
    assert rescued.current_player == "black"


def test_checkmate_rule_counts_legal_command_power_as_an_escape():
    engine, state = make_gambit_play_state()
    assert state.gambit is not None
    state.board.grid[7][4] = None
    state.board.grid[7][7] = create_piece(state, "king", "white")
    state.board.grid[0][0] = create_piece(state, "king", "black")
    state.board.grid[0][7] = create_piece(state, "rook", "black")
    state.board.grid[7][6] = create_piece(state, "pawn", "white")
    state.board.grid[6][6] = create_piece(state, "pawn", "white")
    state.gambit.command_points["white"] = 1

    engine.evaluate_state(state)
    assert state.game_status == "check"
    assert engine.get_valid_moves_for_color(state, "white") == []
    assert engine.has_legal_alternative_action(state, "white") is True


def test_pawn_promotion_is_a_modular_move_rule():
    engine, state = make_gambit_play_state()
    state.board.grid[1][0] = create_piece(state, "pawn", "white")

    promoted, explanation = engine.apply_move(
        state,
        Move(
            fromRow=1,
            fromCol=0,
            toRow=0,
            toCol=0,
            promotion="knight",
        ),
    )
    assert promoted.board.grid[0][0].type == "knight"
    assert "promoted to Knight" in explanation


def test_gambit_create_request_defaults_remain_classic():
    request = CreateGameRequest()
    assert request.variant == "classic"
