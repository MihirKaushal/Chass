import chess
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.catalog import build_default_piece_definitions
from backend.models import Move
from backend.models.schemas import ImportGameRequest
from backend.rules import RuleEngine
from scripts.verification_positions import starting_state


def imported_state(board):
    labels = [[None] * 8 for _ in range(8)]
    for square, piece in board.piece_map().items():
        labels[7 - chess.square_rank(square)][chess.square_file(square)] = (
            f"{'white' if piece.color else 'black'}-{chess.piece_name(piece.piece_type)}"
        )
    payload = ImportGameRequest(
        board=labels,
        reviewConfirmed=True,
        currentPlayer="white" if board.turn else "black",
        castlingRights={
            "whiteKing": board.has_kingside_castling_rights(chess.WHITE),
            "whiteQueen": board.has_queenside_castling_rights(chess.WHITE),
            "blackKing": board.has_kingside_castling_rights(chess.BLACK),
            "blackQueen": board.has_queenside_castling_rights(chess.BLACK),
        },
        enPassant=chess.square_name(board.ep_square) if board.ep_square is not None else None,
        halfmoveClock=board.halfmove_clock,
        fullmoveNumber=board.fullmove_number,
    )
    state, _ = RuleEngine().imports.build(payload, RuleEngine(), build_default_piece_definitions())
    return state


def assert_parity(board, state):
    engine = RuleEngine()
    actual = {
        (m.from_row, m.from_col, m.to_row, m.to_col)
        for m in engine.get_valid_moves_for_current_player(state)
    }
    expected = {
        (
            7 - chess.square_rank(m.from_square),
            chess.square_file(m.from_square),
            7 - chess.square_rank(m.to_square),
            chess.square_file(m.to_square),
        )
        for m in board.legal_moves
    }
    assert actual == expected, board.fen()
    assert engine.is_king_in_check(state, state.current_player) == board.is_check()
    assert (state.game_status == "checkmate") == board.is_checkmate()
    assert (state.game_status == "stalemate") == board.is_stalemate()


@pytest.mark.parametrize(
    "fen",
    [
        chess.STARTING_FEN,
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2",
        "4k3/P7/8/8/8/8/7p/4K3 w - - 0 1",
        "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1",
        "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1",
    ],
)
def test_reference_positions_match_python_chess(fen):
    reference = chess.Board(fen)
    assert_parity(reference, imported_state(reference))


@settings(max_examples=20, deadline=None, derandomize=True)
@given(st.lists(st.integers(min_value=0, max_value=10000), min_size=1, max_size=24))
def test_legal_playouts_preserve_parity_captures_and_input_state(choices):
    reference, state, engine = chess.Board(), starting_state(), RuleEngine()
    for choice in choices:
        assert_parity(reference, state)
        moves = sorted(reference.legal_moves, key=lambda m: m.uci())
        if not moves or state.phase == "finished":
            break
        move = moves[choice % len(moves)]
        before = state.model_dump_json()
        next_state, _ = engine.apply_move(
            state,
            Move(
                fromRow=7 - chess.square_rank(move.from_square),
                fromCol=chess.square_file(move.from_square),
                toRow=7 - chess.square_rank(move.to_square),
                toCol=chess.square_file(move.to_square),
                promotion=chess.piece_name(move.promotion) if move.promotion else None,
            ),
        )
        assert state.model_dump_json() == before, (
            "Search/move application must not mutate the parent"
        )
        captured = reference.is_capture(move)
        assert bool(next_state.history[-1].captures) == captured
        reference.push(move)
        assert {
            (row, col): (piece.color, piece.type)
            for row, rank in enumerate(next_state.board.grid)
            for col, piece in enumerate(rank)
            if piece
        } == {
            (7 - chess.square_rank(square), chess.square_file(square)): (
                "white" if piece.color else "black",
                chess.piece_name(piece.piece_type),
            )
            for square, piece in reference.piece_map().items()
        }
        assert sum(piece is not None for row in next_state.board.grid for piece in row) == len(
            reference.piece_map()
        )
        state = next_state
    assert_parity(reference, state)


@pytest.mark.parametrize("promotion", [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT])
def test_all_promotion_choices_match_reference(promotion):
    reference = chess.Board("4k3/P7/8/8/8/8/7p/4K3 w - - 0 1")
    state = imported_state(reference)
    reference.push(chess.Move(chess.A7, chess.A8, promotion=promotion))
    state, _ = RuleEngine().apply_move(
        state, Move(fromRow=1, fromCol=0, toRow=0, toCol=0, promotion=chess.piece_name(promotion))
    )
    assert state.board.grid[0][0].type == chess.piece_name(promotion)
    assert_parity(reference, state)


@settings(max_examples=25, deadline=None, derandomize=True)
@given(st.integers(6, 16), st.integers(4, 16))
def test_rectangular_legal_moves_stay_in_bounds_and_preserve_kings(rows, cols):
    state, engine = starting_state(rows, cols), RuleEngine()
    for move in engine.get_valid_moves_for_current_player(state):
        assert 0 <= move.to_row < rows and 0 <= move.to_col < cols
        assert 0 <= move.from_row < rows and 0 <= move.from_col < cols
    assert (
        sum(piece is not None and piece.type == "king" for row in state.board.grid for piece in row)
        == 2
    )
