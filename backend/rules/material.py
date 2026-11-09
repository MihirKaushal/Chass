from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations_with_replacement
from typing import Any

from backend.models import PieceDefinition

INSUFFICIENT_MATERIAL_MESSAGE = "Insufficient material."

MATERIAL_CLASSES = {
    "royal",
    "major",
    "minor",
    "bishop",
    "promotable",
    "support",
}


@dataclass(frozen=True)
class MaterialPiece:
    row: int
    col: int
    type: str
    color: str


def _placement_value(placement: object, key: str, default: Any = None) -> Any:
    if isinstance(placement, Mapping):
        return placement.get(key, default)
    return getattr(placement, key, default)


def _material_piece(placement: object) -> MaterialPiece:
    return MaterialPiece(
        row=int(_placement_value(placement, "row", 0)),
        col=int(_placement_value(placement, "col", 0)),
        type=str(_placement_value(placement, "type", "")),
        color=str(_placement_value(placement, "color", "neutral")),
    )


class StartingMaterialRule:
    """Checks whether a configured position can reach its selected victory objective."""

    @staticmethod
    def material_class(
        piece_type: str,
        definitions: Mapping[str, PieceDefinition],
    ) -> str:
        definition = definitions.get(piece_type)
        if definition is None:
            return "support"

        configured = definition.metadata.get("materialClass")
        if configured in MATERIAL_CLASSES:
            return str(configured)

        attacking_patterns = [
            pattern
            for pattern in definition.patterns
            if pattern.mode in {"capture", "both"}
        ]
        if not attacking_patterns:
            return "support"
        repeating_patterns = [pattern for pattern in attacking_patterns if pattern.repeat]
        if repeating_patterns:
            if all(
                pattern.dr != 0
                and pattern.dc != 0
                and abs(pattern.dr) == abs(pattern.dc)
                for pattern in repeating_patterns
            ):
                return "bishop"
            return "major"
        return "minor"

    @classmethod
    def can_give_check(
        cls,
        piece_type: str,
        definitions: Mapping[str, PieceDefinition],
    ) -> bool:
        return cls.material_class(piece_type, definitions) in {
            "major",
            "minor",
            "bishop",
            "promotable",
        }

    @classmethod
    def checkmate_material_is_sufficient(
        cls,
        placements: Iterable[object],
        definitions: Mapping[str, PieceDefinition],
    ) -> bool:
        threats = [
            (piece, cls.material_class(piece.type, definitions))
            for piece in map(_material_piece, placements)
            if piece.color in {"white", "black"} and piece.type != "king"
        ]
        threats = [item for item in threats if item[1] not in {"royal", "support"}]

        if any(material_class in {"major", "promotable"} for _, material_class in threats):
            return True
        if len(threats) < 2:
            return False
        if all(material_class == "bishop" for _, material_class in threats):
            square_colors = {(piece.row + piece.col) % 2 for piece, _ in threats}
            return len(square_colors) > 1
        return True

    @classmethod
    def is_sufficient(
        cls,
        victory_mode: str,
        placements: Iterable[object],
        definitions: Mapping[str, PieceDefinition],
    ) -> bool:
        pieces = [_material_piece(placement) for placement in placements]
        owned_non_kings = [
            piece
            for piece in pieces
            if piece.color in {"white", "black"} and piece.type != "king"
        ]
        if not owned_non_kings:
            return False

        if victory_mode in {"checkmate", "timed", "royal_score"}:
            return cls.checkmate_material_is_sufficient(pieces, definitions)

        if victory_mode == "check_race":
            return all(
                any(
                    piece.color == color
                    and cls.can_give_check(piece.type, definitions)
                    for piece in owned_non_kings
                )
                for color in ("white", "black")
            )

        if victory_mode == "center_dominion":
            return all(
                sum(piece.color == color for piece in pieces) >= 2
                for color in ("white", "black")
            )

        # King Capture, Point Race, Elimination, and Royal Center can all be
        # reached with one additional active piece. Pure King-only starts are
        # rejected consistently for every mode.
        return True

    @classmethod
    def issue(
        cls,
        victory_mode: str,
        placements: Iterable[object],
        definitions: Mapping[str, PieceDefinition],
    ) -> str | None:
        if cls.is_sufficient(victory_mode, placements, definitions):
            return None
        return INSUFFICIENT_MATERIAL_MESSAGE

    @classmethod
    def can_build_sufficient_army(
        cls,
        *,
        victory_mode: str,
        definitions: Mapping[str, PieceDefinition],
        enabled_piece_types: Iterable[str],
        piece_caps: Mapping[str, int],
        piece_costs: Mapping[str, int],
        budget: int,
        max_pieces: int,
    ) -> bool:
        king_cost = int(piece_costs.get("king", 0))
        if max_pieces < 2 or king_cost > budget:
            return False

        candidates = [
            piece_type
            for piece_type in enabled_piece_types
            if piece_type != "king"
            and piece_caps.get(piece_type, 0) > 0
            and piece_type in definitions
        ]
        max_extra_pieces = min(2, max_pieces - 1)
        for count in range(1, max_extra_pieces + 1):
            for selected in combinations_with_replacement(candidates, count):
                selected_counts = Counter(selected)
                if any(
                    selected_count > piece_caps.get(piece_type, 0)
                    for piece_type, selected_count in selected_counts.items()
                ):
                    continue
                total_cost = king_cost + sum(int(piece_costs.get(piece_type, 0)) for piece_type in selected)
                if total_cost > budget:
                    continue
                synthetic = [
                    {"row": 3, "col": 3, "type": "king", "color": "white"},
                    {"row": 0, "col": 3, "type": "king", "color": "black"},
                ]
                for color, row in (("white", 2), ("black", 1)):
                    synthetic.extend(
                        {
                            "row": row,
                            "col": index,
                            "type": piece_type,
                            "color": color,
                        }
                        for index, piece_type in enumerate(selected)
                    )
                if cls.is_sufficient(victory_mode, synthetic, definitions):
                    return True
        return False
