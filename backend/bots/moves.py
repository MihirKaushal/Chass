from __future__ import annotations

from backend.models import GameState, Move
from backend.rules import RuleEngine

PROMOTION_TO_UCI = {
    "queen": "q",
    "rook": "r",
    "bishop": "b",
    "knight": "n",
}


def encode_move_uci(move: Move, *, board_rows: int) -> str:
    def square_name(row: int, col: int) -> str:
        return f"{chr(ord('a') + col)}{board_rows - row}"

    suffix = PROMOTION_TO_UCI.get(move.promotion or "", "")
    return (
        f"{square_name(move.from_row, move.from_col)}"
        f"{square_name(move.to_row, move.to_col)}{suffix}"
    )


def legal_uci_moves(state: GameState, rule_engine: RuleEngine) -> dict[str, Move]:
    legal: dict[str, Move] = {}
    for option in rule_engine.get_valid_moves_for_current_player(state):
        piece = state.board.grid[option.from_row][option.from_col]
        promotions: tuple[str | None, ...] = (None,)
        if (
            piece is not None
            and piece.type == "pawn"
            and option.to_row in {0, state.board.rows - 1}
        ):
            promotions = ("queen", "rook", "bishop", "knight")
        for promotion in promotions:
            move = Move(
                fromRow=option.from_row,
                fromCol=option.from_col,
                toRow=option.to_row,
                toCol=option.to_col,
                promotion=promotion,
            )
            if rule_engine.validate_move(state, move).is_valid:
                legal[encode_move_uci(move, board_rows=state.board.rows)] = move
    return legal
