from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChessPiece:
    type: str
    is_white: bool
    symbol: str
    points: int
    has_moved: bool = False

    @property
    def color(self) -> str:
        return "white" if self.is_white else "black"

    def get_name(self) -> str:
        return f"{self.color.title()} {self.type.title()}"


_PIECE_META = {
    "pawn": {"points": 1, "white": "\u2659", "black": "\u265F"},
    "rook": {"points": 5, "white": "\u2656", "black": "\u265C"},
    "knight": {"points": 3, "white": "\u2658", "black": "\u265E"},
    "bishop": {"points": 3, "white": "\u2657", "black": "\u265D"},
    "queen": {"points": 9, "white": "\u2655", "black": "\u265B"},
    "king": {"points": 67, "white": "\u2654", "black": "\u265A"},
}


def create_piece(piece_type: str, is_white: bool) -> ChessPiece:
    normalized = piece_type.lower()
    if normalized not in _PIECE_META:
        raise ValueError(f"Unsupported piece type: {piece_type}")

    data = _PIECE_META[normalized]
    symbol = data["white"] if is_white else data["black"]
    return ChessPiece(
        type=normalized,
        is_white=is_white,
        symbol=symbol,
        points=data["points"],
    )
