from __future__ import annotations

from dataclasses import dataclass

import ChessPieces


@dataclass
class ChessBoardSquare:
    is_white: bool
    piece: ChessPieces.ChessPiece | None = None

    def as_dict(self) -> dict:
        return {
            "isWhite": self.is_white,
            "piece": None
            if self.piece is None
            else {
                "type": self.piece.type,
                "color": self.piece.color,
                "symbol": self.piece.symbol,
                "points": self.piece.points,
                "hasMoved": self.piece.has_moved,
            },
        }


class ChessBoard:
    def __init__(self, size: int = 8) -> None:
        if size < 4:
            raise ValueError("Board size must be at least 4")
        self.size = size
        self.board = [
            [ChessBoardSquare(is_white=((row + col) % 2 == 0)) for col in range(size)]
            for row in range(size)
        ]
        self.set_board()

    def _back_rank(self) -> list[str]:
        rank = ["pawn"] * self.size
        cycle = ["rook", "knight", "bishop"]
        left = 0
        right = self.size - 1
        cycle_index = 0

        while right - left + 1 > 2:
            piece_type = cycle[cycle_index % len(cycle)]
            rank[left] = piece_type
            rank[right] = piece_type
            left += 1
            right -= 1
            cycle_index += 1

        if self.size % 2 == 0:
            rank[left] = "queen"
            rank[right] = "king"
        else:
            rank[left] = "king"

        return rank

    def set_board(self) -> None:
        back_rank = self._back_rank()

        for col, piece_type in enumerate(back_rank):
            self.board[0][col].piece = ChessPieces.create_piece(piece_type, False)
            self.board[self.size - 1][col].piece = ChessPieces.create_piece(piece_type, True)

        for col in range(self.size):
            self.board[1][col].piece = ChessPieces.create_piece("pawn", False)
            self.board[self.size - 2][col].piece = ChessPieces.create_piece("pawn", True)

    def move(self, from_row: int, from_col: int, to_row: int, to_col: int) -> dict:
        moving_piece = self.board[from_row][from_col].piece
        if moving_piece is None:
            raise ValueError("No piece found at source square")

        captured_piece = self.board[to_row][to_col].piece

        self.board[from_row][from_col].piece = None
        moving_piece.has_moved = True
        self.board[to_row][to_col].piece = moving_piece

        return {
            "from": {"row": from_row, "col": from_col},
            "to": {"row": to_row, "col": to_col},
            "piece": moving_piece.get_name(),
            "captured": None if captured_piece is None else captured_piece.get_name(),
        }

    def to_json(self) -> dict:
        return {
            "size": self.size,
            "board": [[square.as_dict() for square in row] for row in self.board],
        }
