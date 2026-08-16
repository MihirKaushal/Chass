from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from backend.models import MovePattern, PieceDefinition

STANDARD_PIECE_TYPES = ("pawn", "knight", "bishop", "rook", "queen", "king")
CUSTOM_PIECE_TYPES = (
    "maharani",
    "catapult",
    "barricade",
    "hypnotizer",
    "diplomat",
    "cannibal",
    "elephant",
)
CLASSIC_BACK_RANK = ("rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook")
DEFAULT_DRAFT_POOL_COUNTS = {
    "pawn": 16,
    "knight": 4,
    "bishop": 4,
    "rook": 4,
    "queen": 2,
    "king": 2,
}


def _parameter(
    parameter_id: str,
    label: str,
    description: str,
    default: int,
    minimum: int,
    maximum: int,
    unit: str,
) -> dict[str, Any]:
    return {
        "id": parameter_id,
        "label": label,
        "description": description,
        "default": default,
        "min": minimum,
        "max": maximum,
        "unit": unit,
    }


def _render_template(template: str, values: dict[str, int]) -> str:
    rendered = template.format_map(values)

    def pluralize(match: re.Match[str]) -> str:
        value = int(match.group(1))
        modifier = match.group(2)
        unit = match.group(3)
        return f"{value} {modifier}{unit if value == 1 else f'{unit}s'}"

    return re.sub(
        (
            r"\b(\d+) ((?:own |Cannibal |affected-player |allied )?)"
            r"(square|turn|move|blocker|time|use|pacification|piece)\(s\)"
        ),
        pluralize,
        rendered,
    )


def _normalize_values(
    specs: list[dict[str, Any]],
    supplied: dict[str, int] | None,
    owner_name: str,
) -> dict[str, int]:
    supplied = supplied or {}
    spec_map = {spec["id"]: spec for spec in specs}
    unknown = sorted(set(supplied) - set(spec_map))
    if unknown:
        raise ValueError(f"Unknown {owner_name} setting: {unknown[0]}")

    normalized: dict[str, int] = {}
    for parameter_id, spec in spec_map.items():
        value = supplied.get(parameter_id, spec["default"])
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{owner_name} {spec['label']} must be a whole number")
        if value < spec["min"] or value > spec["max"]:
            raise ValueError(
                f"{owner_name} {spec['label']} must be between "
                f"{spec['min']} and {spec['max']}"
            )
        normalized[parameter_id] = value
    return normalized


def configure_piece_definition(
    definition: PieceDefinition,
    supplied: dict[str, int] | None = None,
) -> tuple[PieceDefinition, dict[str, int]]:
    configured = definition.model_copy(deep=True)
    attributes = deepcopy(configured.custom_attributes)
    specs = list(attributes.get("tunableParameters", []))
    values = _normalize_values(specs, supplied, configured.display_name)
    if not specs:
        return configured, values

    configured.description = _render_template(
        attributes.get("descriptionTemplate", configured.description), values
    )
    configured.movement_summary = _render_template(
        attributes.get("movementTemplate", configured.movement_summary), values
    )
    attributes["rules"] = [
        _render_template(template, values)
        for template in attributes.get("ruleTemplates", attributes.get("rules", []))
    ]
    attributes["configuredParameters"] = [
        {**spec, "value": values[spec["id"]]} for spec in specs
    ]
    configured.custom_attributes = attributes

    # Pattern-backed pieces receive their configured movement range here. More
    # specialized behavior remains in its dedicated rule class.
    movement_distance = values.get("movementDistance")
    if configured.type == "catapult" and movement_distance is not None:
        configured.patterns = [
            pattern
            for distance in range(1, movement_distance + 1)
            for pattern in (
                MovePattern(
                    dr=-distance,
                    dc=0,
                    mode="both",
                    relative_to_color=True,
                    requires_clear_path=distance > 1,
                ),
                MovePattern(
                    dr=-distance,
                    dc=-distance,
                    mode="move",
                    relative_to_color=True,
                    requires_clear_path=distance > 1,
                ),
                MovePattern(
                    dr=-distance,
                    dc=distance,
                    mode="move",
                    relative_to_color=True,
                    requires_clear_path=distance > 1,
                ),
            )
        ]
    elif configured.type == "hypnotizer" and movement_distance is not None:
        configured.patterns = [
            pattern
            for distance in range(1, movement_distance + 1)
            for pattern in (
                MovePattern(
                    dr=-distance,
                    dc=0,
                    mode="move",
                    relative_to_color=True,
                    requires_clear_path=distance > 1,
                ),
                MovePattern(
                    dr=0,
                    dc=-distance,
                    mode="move",
                    relative_to_color=False,
                    requires_clear_path=distance > 1,
                ),
                MovePattern(
                    dr=0,
                    dc=distance,
                    mode="move",
                    relative_to_color=False,
                    requires_clear_path=distance > 1,
                ),
            )
        ]
    elif configured.type == "diplomat" and movement_distance is not None:
        configured.patterns = [
            MovePattern(
                dr=dr * distance,
                dc=dc * distance,
                mode="move",
                relative_to_color=False,
                requires_clear_path=distance > 1,
            )
            for distance in range(1, movement_distance + 1)
            for dr, dc in (
                (-1, -1),
                (-1, 0),
                (-1, 1),
                (0, -1),
                (0, 1),
                (1, -1),
                (1, 0),
                (1, 1),
            )
        ]
    return configured, values


def configure_special_ability(
    ability: dict[str, Any],
    supplied: dict[str, int] | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    configured = deepcopy(ability)
    specs = list(configured.get("tunableParameters", []))
    values = _normalize_values(specs, supplied, configured["name"])
    configured["summary"] = _render_template(
        configured.get("summaryTemplate", configured["summary"]), values
    )
    configured["details"] = [
        _render_template(template, values)
        for template in configured.get("detailTemplates", configured.get("details", []))
    ]
    configured["configuredParameters"] = [
        {**spec, "value": values[spec["id"]]} for spec in specs
    ]
    for legacy_key in ("cooldownTurns", "usageLimit"):
        parameter_id = configured.get(f"{legacy_key}Parameter")
        if parameter_id:
            configured[legacy_key] = values[parameter_id]
    return configured, values


def normalize_piece_parameters(
    supplied: dict[str, dict[str, int]],
    definitions: dict[str, PieceDefinition] | None = None,
) -> dict[str, dict[str, int]]:
    catalog = definitions or build_catalog_piece_definitions()
    unknown = sorted(set(supplied) - set(catalog))
    if unknown:
        raise ValueError(f"Unknown piece parameter group: {unknown[0]}")
    return {
        piece_type: configure_piece_definition(definition, supplied.get(piece_type))[1]
        for piece_type, definition in catalog.items()
        if definition.custom_attributes.get("tunableParameters")
    }


def normalize_ability_parameters(
    supplied: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    abilities = {ability["id"]: ability for ability in SPECIAL_ABILITIES}
    unknown = sorted(set(supplied) - set(abilities))
    if unknown:
        raise ValueError(f"Unknown ability parameter group: {unknown[0]}")
    return {
        ability_id: configure_special_ability(ability, supplied.get(ability_id))[1]
        for ability_id, ability in abilities.items()
    }


def build_default_draft_pool(piece_types: set[str] | list[str]) -> dict[str, int]:
    return {
        piece_type: DEFAULT_DRAFT_POOL_COUNTS.get(piece_type, 2)
        for piece_type in piece_types
        if piece_type != "barricade"
    }


def adaptive_back_rank(cols: int) -> list[str]:
    if cols >= len(CLASSIC_BACK_RANK):
        return list(CLASSIC_BACK_RANK)

    rank = ["pawn"] * cols
    left = 0
    right = cols - 1
    cycle = ("rook", "knight", "bishop")
    cycle_index = 0
    while right - left + 1 > 2:
        piece_type = cycle[cycle_index % len(cycle)]
        rank[left] = piece_type
        rank[right] = piece_type
        left += 1
        right -= 1
        cycle_index += 1

    if cols % 2 == 0:
        rank[left] = "queen"
        rank[right] = "king"
    else:
        rank[left] = "king"
    return rank


def classic_layout(rows: int = 8, cols: int = 8) -> list[dict[str, Any]]:
    back_rank = adaptive_back_rank(cols)
    start_col = (cols - len(back_rank)) // 2
    placements: list[dict[str, Any]] = []
    for index, piece_type in enumerate(back_rank):
        col = start_col + index
        placements.extend(
            [
                {"row": 0, "col": col, "type": piece_type, "color": "black"},
                {"row": 1, "col": col, "type": "pawn", "color": "black"},
                {"row": rows - 2, "col": col, "type": "pawn", "color": "white"},
                {"row": rows - 1, "col": col, "type": piece_type, "color": "white"},
            ]
        )
    return placements


def formation_layout(formation_id: str) -> tuple[int, int, list[dict[str, Any]]]:
    if formation_id == "no_pawns":
        return 8, 8, [piece for piece in classic_layout() if piece["type"] != "pawn"]
    if formation_id == "pawn_race":
        return 8, 8, [piece for piece in classic_layout() if piece["type"] in {"pawn", "king"}]
    if formation_id == "knight_skirmish":
        return (
            6,
            6,
            [
                {"row": 0, "col": 2, "type": "king", "color": "black"},
                {"row": 1, "col": 1, "type": "knight", "color": "black"},
                {"row": 1, "col": 4, "type": "knight", "color": "black"},
                {"row": 5, "col": 3, "type": "king", "color": "white"},
                {"row": 4, "col": 1, "type": "knight", "color": "white"},
                {"row": 4, "col": 4, "type": "knight", "color": "white"},
            ],
        )
    if formation_id == "horde":
        placements = [piece for piece in classic_layout() if piece["color"] == "black"]
        placements.append({"row": 7, "col": 4, "type": "king", "color": "white"})
        placements.extend(
            {"row": row, "col": col, "type": "pawn", "color": "white"}
            for row in (4, 5, 6)
            for col in range(8)
        )
        return 8, 8, placements
    if formation_id == "castle_siege":
        placements = classic_layout(8, 10)
        for color, back_row, pawn_row in (("black", 0, 1), ("white", 7, 6)):
            for col in (0, 9):
                placements.append({"row": back_row, "col": col, "type": "rook", "color": color})
                placements.append({"row": pawn_row, "col": col, "type": "pawn", "color": color})
        return 8, 10, placements
    return 8, 8, classic_layout()


def _queen_patterns() -> list[MovePattern]:
    return [
        MovePattern(dr=1, dc=0, repeat=True, requires_clear_path=True),
        MovePattern(dr=-1, dc=0, repeat=True, requires_clear_path=True),
        MovePattern(dr=0, dc=1, repeat=True, requires_clear_path=True),
        MovePattern(dr=0, dc=-1, repeat=True, requires_clear_path=True),
        MovePattern(dr=1, dc=1, repeat=True, requires_clear_path=True),
        MovePattern(dr=1, dc=-1, repeat=True, requires_clear_path=True),
        MovePattern(dr=-1, dc=1, repeat=True, requires_clear_path=True),
        MovePattern(dr=-1, dc=-1, repeat=True, requires_clear_path=True),
    ]


def _knight_patterns() -> list[MovePattern]:
    return [
        MovePattern(dr=dr, dc=dc)
        for dr, dc in (
            (-2, -1),
            (-2, 1),
            (-1, -2),
            (-1, 2),
            (1, -2),
            (1, 2),
            (2, -1),
            (2, 1),
        )
    ]


def build_catalog_piece_definitions() -> dict[str, PieceDefinition]:
    pieces = {
        "pawn": PieceDefinition(
            type="pawn",
            display_name="Pawn",
            symbols={"white": "♙", "black": "♟"},
            icon="♟",
            description="A low-cost foot soldier that advances toward the opposite edge.",
            movement_summary=(
                "Moves one square forward, or two from its starting square. "
                "Captures one square diagonally forward and promotes on the final rank."
            ),
            points=1,
            patterns=[
                MovePattern(
                    dr=-1,
                    dc=0,
                    mode="move",
                    relative_to_color=True,
                    requires_clear_path=True,
                ),
                MovePattern(
                    dr=-2,
                    dc=0,
                    mode="move",
                    relative_to_color=True,
                    requires_unmoved=True,
                    requires_clear_path=True,
                ),
                MovePattern(dr=-1, dc=1, mode="capture", relative_to_color=True),
                MovePattern(dr=-1, dc=-1, mode="capture", relative_to_color=True),
            ],
            metadata={"family": "classic"},
        ),
        "rook": PieceDefinition(
            type="rook",
            display_name="Rook",
            symbols={"white": "♖", "black": "♜"},
            icon="♜",
            description=(
                "A heavy line piece that controls ranks and files and can be sacrificed "
                "to clear a Barricade."
            ),
            movement_summary=(
                "Moves any number of clear squares horizontally or vertically. It may "
                "sacrifice itself to demolish the first visible Barricade on that line."
            ),
            points=5,
            patterns=[
                MovePattern(dr=1, dc=0, repeat=True, requires_clear_path=True),
                MovePattern(dr=-1, dc=0, repeat=True, requires_clear_path=True),
                MovePattern(dr=0, dc=1, repeat=True, requires_clear_path=True),
                MovePattern(dr=0, dc=-1, repeat=True, requires_clear_path=True),
            ],
            metadata={"family": "classic"},
        ),
        "knight": PieceDefinition(
            type="knight",
            display_name="Knight",
            symbols={"white": "♘", "black": "♞"},
            icon="♞",
            description="A mobile piece whose unusual route reaches around normal blockers.",
            movement_summary=(
                "Moves in an L shape: two squares in one direction and one perpendicular. "
                "A Barricade blocks jumps that cross its area."
            ),
            points=3,
            patterns=_knight_patterns(),
            metadata={"family": "classic"},
        ),
        "bishop": PieceDefinition(
            type="bishop",
            display_name="Bishop",
            symbols={"white": "♗", "black": "♝"},
            icon="♝",
            description="A long-range piece permanently tied to one square color.",
            movement_summary="Moves any number of clear squares diagonally.",
            points=3,
            patterns=[
                MovePattern(dr=1, dc=1, repeat=True, requires_clear_path=True),
                MovePattern(dr=1, dc=-1, repeat=True, requires_clear_path=True),
                MovePattern(dr=-1, dc=1, repeat=True, requires_clear_path=True),
                MovePattern(dr=-1, dc=-1, repeat=True, requires_clear_path=True),
            ],
            metadata={"family": "classic"},
        ),
        "queen": PieceDefinition(
            type="queen",
            display_name="Queen",
            symbols={"white": "♕", "black": "♛"},
            icon="♛",
            description="The strongest standard piece, combining rook and bishop mobility.",
            movement_summary="Moves any number of clear squares in any straight direction.",
            points=9,
            patterns=_queen_patterns(),
            metadata={"family": "classic"},
        ),
        "king": PieceDefinition(
            type="king",
            display_name="King",
            symbols={"white": "♔", "black": "♚"},
            icon="♚",
            description="The royal piece. Its importance depends on the selected victory rule.",
            movement_summary="Moves one square in any direction and may not enter an attacked square.",
            points=None,
            patterns=[
                MovePattern(dr=1, dc=0),
                MovePattern(dr=-1, dc=0),
                MovePattern(dr=0, dc=1),
                MovePattern(dr=0, dc=-1),
                MovePattern(dr=1, dc=1),
                MovePattern(dr=1, dc=-1),
                MovePattern(dr=-1, dc=1),
                MovePattern(dr=-1, dc=-1),
            ],
            metadata={"family": "classic"},
        ),
        "maharani": PieceDefinition(
            type="maharani",
            display_name="Maharani",
            symbols={"white": "✧", "black": "✦"},
            icon="✦",
            description=(
                "A royal powerhouse combining queen and knight mobility with one controlled jump."
            ),
            movement_summary=(
                "Moves like a queen or knight. On a queen line it may cross exactly one occupied "
                "square, but never a Barricade."
            ),
            points=13,
            is_custom=True,
            behavior="maharani",
            patterns=[*_queen_patterns(), *_knight_patterns()],
            custom_attributes={
                "tunableParameters": [
                    _parameter(
                        "blockersCrossed",
                        "Blockers Crossed",
                        "Occupied squares a queen-line jump must cross before landing.",
                        1,
                        1,
                        8,
                        "blocker",
                    ),
                ],
                "descriptionTemplate": (
                    "A royal powerhouse combining queen and knight mobility with a controlled "
                    "{blockersCrossed}-blocker jump."
                ),
                "movementTemplate": (
                    "Moves like a queen or knight. On a queen line it may cross exactly "
                    "{blockersCrossed} occupied square(s), but never a Barricade."
                ),
                "ruleTemplates": [
                    "Queen movement",
                    "Knight movement",
                    "May cross exactly {blockersCrossed} blocker(s)",
                ],
            },
            metadata={"family": "chass_custom", "visualKey": "maharani"},
        ),
        "catapult": PieceDefinition(
            type="catapult",
            display_name="Catapult",
            symbols={"white": "◇", "black": "◆"},
            icon="◈",
            description=(
                "A forward siege piece that fires over one or two squares, then must recover."
            ),
            movement_summary=(
                "Moves one square forward or diagonally forward. It captures directly ahead, "
                "or fires along one of those three forward lanes."
            ),
            points=5,
            is_custom=True,
            behavior="catapult",
            patterns=[
                MovePattern(dr=-1, dc=0, mode="both", relative_to_color=True),
                MovePattern(dr=-1, dc=-1, mode="move", relative_to_color=True),
                MovePattern(dr=-1, dc=1, mode="move", relative_to_color=True),
            ],
            custom_attributes={
                "tunableParameters": [
                    _parameter(
                        "movementDistance",
                        "Movement Distance",
                        "Maximum number of forward squares the Catapult may move.",
                        1,
                        1,
                        8,
                        "square",
                    ),
                    _parameter(
                        "shortProjectileSkip",
                        "Short Projectile Skip",
                        "Squares crossed before the short projectile reaches its target.",
                        1,
                        1,
                        14,
                        "square",
                    ),
                    _parameter(
                        "shortRecoveryTurns",
                        "Short Recovery",
                        "Own turns required before firing or moving after the short shot.",
                        2,
                        0,
                        50,
                        "turn",
                    ),
                    _parameter(
                        "longProjectileSkip",
                        "Long Projectile Skip",
                        "Squares crossed before the long projectile reaches its target.",
                        2,
                        1,
                        14,
                        "square",
                    ),
                    _parameter(
                        "longRecoveryTurns",
                        "Long Recovery",
                        "Own turns required before firing or moving after the long shot.",
                        4,
                        0,
                        50,
                        "turn",
                    ),
                ],
                "descriptionTemplate": (
                    "A forward siege piece with projectile paths that skip "
                    "{shortProjectileSkip} or {longProjectileSkip} square(s), then recover."
                ),
                "movementTemplate": (
                    "Moves up to {movementDistance} clear square(s) forward or diagonally "
                    "forward. It captures directly ahead or fires along those three lanes."
                ),
                "ruleTemplates": [
                    "Projectile over {shortProjectileSkip} square(s): recover for "
                    "{shortRecoveryTurns} own turn(s)",
                    "Projectile over {longProjectileSkip} square(s): recover for "
                    "{longRecoveryTurns} own turn(s)",
                    "Barricades block projectiles",
                ],
            },
            metadata={"family": "chass_custom", "visualKey": "catapult"},
        ),
        "barricade": PieceDefinition(
            type="barricade",
            display_name="Barricade",
            symbols={"white": "▦", "black": "▦", "neutral": "▦"},
            icon="▦",
            description=(
                "A neutral wall that blocks movement and projectiles without attacking anything."
            ),
            movement_summary=(
                "Either player may move it one adjacent square when one of their pieces touches it. "
                "It cannot capture or be captured normally. A visible Rook may sacrifice "
                "itself to remove it."
            ),
            points=0,
            is_custom=True,
            behavior="barricade",
            patterns=[],
            custom_attributes={
                "tunableParameters": [
                    _parameter(
                        "movementDistance",
                        "Movement Distance",
                        "Maximum clear distance either player may reposition the wall.",
                        1,
                        1,
                        8,
                        "square",
                    ),
                    _parameter(
                        "controlRange",
                        "Control Range",
                        "Distance within which a player's piece allows that player to move it.",
                        1,
                        1,
                        8,
                        "square",
                    ),
                ],
                "descriptionTemplate": (
                    "A neutral wall that blocks movement and projectiles without attacking anything."
                ),
                "movementTemplate": (
                    "Either player may move it up to {movementDistance} clear square(s) when one "
                    "of their pieces is within {controlRange} square(s). It cannot capture or be "
                    "captured normally. A visible Rook may sacrifice itself to remove it."
                ),
                "ruleTemplates": [
                    "Neutral",
                    "Blocks jumps and projectiles",
                    "Controlled by a friendly piece within {controlRange} square(s)",
                    "A Rook can sacrifice itself to demolish it",
                ],
            },
            metadata={
                "family": "chass_custom",
                "neutral": True,
                "visualKey": "barricade",
            },
        ),
        "hypnotizer": PieceDefinition(
            type="hypnotizer",
            display_name="Hypnotizer",
            symbols={"white": "◎", "black": "◉"},
            icon="◉",
            description=(
                "A conversion specialist that recruits one adjacent enemy after sustained contact."
            ),
            movement_summary=(
                "Moves one or two clear squares forward or sideways. It cannot move backward or "
                "capture normally."
            ),
            points=6,
            is_custom=True,
            behavior="hypnotizer",
            patterns=[
                MovePattern(dr=-1, dc=0, mode="move", relative_to_color=True),
                MovePattern(
                    dr=-2,
                    dc=0,
                    mode="move",
                    relative_to_color=True,
                    requires_clear_path=True,
                ),
                MovePattern(dr=0, dc=-1, mode="move", relative_to_color=False),
                MovePattern(dr=0, dc=1, mode="move", relative_to_color=False),
                MovePattern(
                    dr=0,
                    dc=-2,
                    mode="move",
                    relative_to_color=False,
                    requires_clear_path=True,
                ),
                MovePattern(
                    dr=0,
                    dc=2,
                    mode="move",
                    relative_to_color=False,
                    requires_clear_path=True,
                ),
            ],
            custom_attributes={
                "tunableParameters": [
                    _parameter(
                        "movementDistance",
                        "Movement Distance",
                        "Maximum clear distance it may move forward or sideways.",
                        2,
                        1,
                        8,
                        "square",
                    ),
                    _parameter(
                        "weakContactTurns",
                        "Weak Piece Contact",
                        "Contact turns needed to recruit a piece worth 3 points or fewer.",
                        3,
                        1,
                        50,
                        "turn",
                    ),
                    _parameter(
                        "mediumContactTurns",
                        "Medium Piece Contact",
                        "Contact turns needed to recruit a piece worth 4 or 5 points.",
                        4,
                        1,
                        50,
                        "turn",
                    ),
                    _parameter(
                        "strongContactTurns",
                        "Strong Piece Contact",
                        "Contact turns needed to recruit a piece worth 6 points or more.",
                        5,
                        1,
                        50,
                        "turn",
                    ),
                ],
                "descriptionTemplate": (
                    "A conversion specialist that recruits one adjacent enemy after sustained contact."
                ),
                "movementTemplate": (
                    "Moves up to {movementDistance} clear square(s) forward or sideways. "
                    "It cannot move backward or capture normally."
                ),
                "ruleTemplates": [
                    "One recruitment target",
                    "Kings cannot be recruited",
                    "Weak pieces recruit after {weakContactTurns} contact turn(s)",
                    "Medium pieces recruit after {mediumContactTurns} contact turn(s)",
                    "Strong pieces recruit after {strongContactTurns} contact turn(s)",
                    "Contact progress resets if separated",
                ],
            },
            metadata={"family": "chass_custom", "visualKey": "hypnotizer"},
        ),
        "diplomat": PieceDefinition(
            type="diplomat",
            display_name="Diplomat",
            symbols={"white": "⚜", "black": "⚜"},
            icon="⚜",
            description=("A protected peacekeeper that temporarily pacifies nearby enemy pieces."),
            movement_summary=(
                "Moves one square in any direction. It cannot capture or be captured. After two "
                "contact turns it pacifies an enemy for five of that enemy's turns."
            ),
            points=4,
            is_custom=True,
            behavior="diplomat",
            patterns=[
                MovePattern(dr=dr, dc=dc, mode="move", relative_to_color=False)
                for dr, dc in (
                    (-1, -1),
                    (-1, 0),
                    (-1, 1),
                    (0, -1),
                    (0, 1),
                    (1, -1),
                    (1, 0),
                    (1, 1),
                )
            ],
            custom_attributes={
                "tunableParameters": [
                    _parameter(
                        "movementDistance",
                        "Movement Distance",
                        "Maximum clear distance the Diplomat may move in any direction.",
                        1,
                        1,
                        8,
                        "square",
                    ),
                    _parameter(
                        "contactTurns",
                        "Contact To Pacify",
                        "Consecutive contact turns required to pacify an enemy.",
                        2,
                        1,
                        50,
                        "turn",
                    ),
                    _parameter(
                        "pacifiedTurns",
                        "Pacification Duration",
                        "Affected player's turns that the target remains pacified.",
                        5,
                        1,
                        50,
                        "turn",
                    ),
                    _parameter(
                        "retireAfterPacifications",
                        "Retirement Threshold",
                        "Successful pacifications before the Diplomat retires.",
                        5,
                        1,
                        50,
                        "pacification",
                    ),
                ],
                "descriptionTemplate": (
                    "A protected peacekeeper that temporarily pacifies nearby enemy pieces."
                ),
                "movementTemplate": (
                    "Moves up to {movementDistance} clear square(s) in any direction. It cannot "
                    "capture or be captured. After {contactTurns} contact turn(s), it pacifies an "
                    "enemy for {pacifiedTurns} of that enemy's turns."
                ),
                "ruleTemplates": [
                    "Uncapturable",
                    "Can pacify any enemy piece, including a King",
                    "Pacifies after {contactTurns} contact turn(s)",
                    "Pacification lasts {pacifiedTurns} affected-player turn(s)",
                    "Retires after {retireAfterPacifications} pacification(s)",
                ],
            },
            metadata={"family": "chass_custom", "visualKey": "diplomat"},
        ),
        "cannibal": PieceDefinition(
            type="cannibal",
            display_name="Cannibal",
            symbols={"white": "◖", "black": "◗"},
            icon="◗",
            description=(
                "A shape-stealing piece that consumes pieces behind it, including allies, "
                "then borrows their movement for five of its own moves."
            ),
            movement_summary=(
                "Normally moves one square in any direction, but consumes only directly "
                "backward or diagonally backward. After consuming, it uses the victim's "
                "movement for five Cannibal moves and cannot capture during that form."
            ),
            points=6,
            is_custom=True,
            behavior="cannibal",
            patterns=[
                MovePattern(dr=dr, dc=dc, relative_to_color=False)
                for dr, dc in (
                    (-1, -1),
                    (-1, 0),
                    (-1, 1),
                    (0, -1),
                    (0, 1),
                    (1, -1),
                    (1, 0),
                    (1, 1),
                )
            ],
            custom_attributes={
                "tunableParameters": [
                    _parameter(
                        "movementDistance",
                        "Base Movement Distance",
                        "Maximum clear distance it may move before borrowing mobility.",
                        1,
                        1,
                        8,
                        "square",
                    ),
                    _parameter(
                        "consumeDistance",
                        "Consume Distance",
                        "Maximum clear backward distance from which it may consume a piece.",
                        1,
                        1,
                        8,
                        "square",
                    ),
                    _parameter(
                        "borrowedMovementMoves",
                        "Borrowed Movement",
                        "Cannibal moves for which the consumed piece's movement remains active.",
                        5,
                        1,
                        50,
                        "move",
                    ),
                ],
                "descriptionTemplate": (
                    "A shape-stealing piece that consumes pieces behind it, including allies, "
                    "then borrows their movement for {borrowedMovementMoves} of its own moves."
                ),
                "movementTemplate": (
                    "Normally moves up to {movementDistance} clear square(s) in any direction, "
                    "but consumes only up to {consumeDistance} square(s) directly or diagonally "
                    "backward. After consuming, it uses the victim's movement for "
                    "{borrowedMovementMoves} Cannibal moves and cannot capture during that form."
                ),
                "ruleTemplates": [
                    "May consume allied or enemy pieces only behind it",
                    "Borrows the consumed piece's movement for {borrowedMovementMoves} Cannibal move(s)",
                    "Cannot capture while using borrowed movement",
                    "Consuming another Cannibal grants Queen mobility",
                    "Cannot be revived by Necromancy",
                ],
            },
            metadata={"family": "chass_custom", "visualKey": "cannibal"},
        ),
        "elephant": PieceDefinition(
            type="elephant",
            display_name="Elephant",
            symbols={"white": "E", "black": "e"},
            icon="E",
            description=(
                "A forward-driving heavy piece that moves without capturing or charges "
                "through a short lane to remove its occupants."
            ),
            movement_summary=(
                "Moves forward or sideways up to four clear squares without capturing. "
                "Its two-square charge removes pieces on both traversed squares."
            ),
            points=7,
            is_custom=True,
            behavior="elephant",
            patterns=[],
            custom_attributes={
                "tunableParameters": [
                    _parameter(
                        "movementDistance",
                        "Movement Distance",
                        "Maximum clear distance for a non-capturing forward or sideways move.",
                        4,
                        1,
                        16,
                        "square",
                    ),
                    _parameter(
                        "chargeDistance",
                        "Charge Distance",
                        "Exact number of forward or sideways squares covered by a charge.",
                        2,
                        1,
                        16,
                        "square",
                    ),
                    _parameter(
                        "alliedChargeLimit",
                        "Allied Charge Limit",
                        "Maximum allied pieces that a single charge may remove.",
                        1,
                        0,
                        16,
                        "piece",
                    ),
                ],
                "descriptionTemplate": (
                    "A forward-driving heavy piece that moves without capturing or charges "
                    "through a short lane to remove its occupants."
                ),
                "movementTemplate": (
                    "Moves forward or sideways up to {movementDistance} clear square(s) "
                    "without capturing. A charge travels exactly {chargeDistance} square(s) "
                    "and removes every permitted piece on those squares. It never moves backward."
                ),
                "ruleTemplates": [
                    "A charge may remove up to {alliedChargeLimit} allied piece(s)",
                    "Cannot charge through a Barricade, protected piece, or unavailable square",
                    "Cannot charge through its own King",
                    "Charging another Elephant eliminates both Elephants",
                    "Cannot be consumed by a Cannibal",
                ],
            },
            metadata={"family": "chass_custom", "visualKey": "elephant"},
        ),
    }
    return pieces


def build_default_piece_definitions() -> dict[str, PieceDefinition]:
    catalog = build_catalog_piece_definitions()
    return {piece_type: catalog[piece_type] for piece_type in STANDARD_PIECE_TYPES}


SPECIAL_ABILITIES: list[dict[str, Any]] = [
    {
        "id": "necromancy",
        "name": "Necromancy",
        "icon": "☠",
        "summary": "Spend earned score to recruit a captured enemy piece, then recharge for 9 turns.",
        "summaryTemplate": (
            "Spend earned score to recruit a captured enemy piece, then recharge for "
            "{cooldownTurns} turn(s)."
        ),
        "cooldownTurns": 9,
        "cooldownTurnsParameter": "cooldownTurns",
        "tunableParameters": [
            _parameter(
                "cooldownTurns",
                "Recharge",
                "Own turns before Necromancy can be used again.",
                9,
                0,
                50,
                "turn",
            ),
        ],
        "detailTemplates": [
            "The recruited piece changes to your color.",
            "Its price is its configured point value and spending lowers your score.",
            "Kings, Cannibals, neutral pieces, and unaffordable pieces cannot be recruited.",
            "Deployment requires an empty square in your home rows, consumes a turn, and starts "
            "a {cooldownTurns}-turn recharge.",
        ],
        "details": [],
    },
    {
        "id": "getaway",
        "name": "Getaway",
        "icon": "⇄",
        "summary": "Once per match, escape checkmate by swapping the King with your Queen.",
        "summaryTemplate": (
            "Escape checkmate up to {usesPerGame} time(s) per match by swapping the King "
            "with your Queen."
        ),
        "usageLimit": 1,
        "usageLimitParameter": "usesPerGame",
        "tunableParameters": [
            _parameter(
                "usesPerGame",
                "Uses Per Game",
                "Successful royal escapes available to each player.",
                1,
                1,
                20,
                "use",
            ),
        ],
        "detailTemplates": [
            "Only a Queen of the same color can be the swap partner.",
            "The swap is available only when it produces a legal position.",
            "If no legal partner exists, checkmate ends the game normally.",
            "Each player may complete {usesPerGame} successful Getaway use(s) per match.",
        ],
        "details": [],
    },
    {
        "id": "eye_for_an_eye",
        "name": "Eye for an Eye",
        "icon": "⚖",
        "summary": "Trade matching pieces, then wait 10 turns before using the ability again.",
        "summaryTemplate": (
            "Trade matching pieces, then wait {cooldownTurns} turn(s) before using the "
            "ability again."
        ),
        "cooldownTurns": 10,
        "cooldownTurnsParameter": "cooldownTurns",
        "tunableParameters": [
            _parameter(
                "cooldownTurns",
                "Recharge",
                "Own turns before Eye for an Eye can be used again.",
                10,
                0,
                50,
                "turn",
            ),
        ],
        "detailTemplates": [
            "A successful trade consumes the turn and starts a {cooldownTurns}-turn cooldown.",
            "Kings and neutral pieces cannot be selected.",
            "Neither removal awards score and it cannot be used while in check.",
        ],
        "details": [],
    },
    {
        "id": "kamikaze",
        "name": "Kamikaze",
        "icon": "✹",
        "summary": "A final-rank Pawn may detonate instead of promoting.",
        "summaryTemplate": (
            "A final-rank Pawn may detonate across {blastRadius} horizontal square(s) "
            "instead of promoting."
        ),
        "tunableParameters": [
            _parameter(
                "blastRadius",
                "Blast Radius",
                "Horizontal squares affected on each side of the Pawn.",
                2,
                1,
                15,
                "square",
            ),
        ],
        "detailTemplates": [
            "The Pawn is sacrificed and enemies up to {blastRadius} horizontal square(s) "
            "away are removed.",
            "A Barricade stops the blast from continuing past it.",
            "An enemy King in range causes an immediate ability victory.",
        ],
        "details": [],
    },
    {
        "id": "episcopal",
        "name": "Episcopal",
        "icon": "✝",
        "summary": "Every 6 turns, shift a Bishop 1 square onto the opposite color.",
        "summaryTemplate": (
            "Every {cooldownTurns} turn(s), shift a Bishop up to {shiftDistance} "
            "square(s) horizontally or vertically."
        ),
        "cooldownTurns": 6,
        "cooldownTurnsParameter": "cooldownTurns",
        "tunableParameters": [
            _parameter(
                "cooldownTurns",
                "Recharge",
                "Own turns before another Episcopal shift is available.",
                6,
                0,
                50,
                "turn",
            ),
            _parameter(
                "shiftDistance",
                "Shift Distance",
                "Maximum clear horizontal or vertical distance for the Bishop shift.",
                1,
                1,
                15,
                "square",
            ),
        ],
        "detailTemplates": [
            "The shift travels up to {shiftDistance} clear square(s) horizontally or vertically "
            "and may capture an enemy on its destination.",
            "It consumes the turn and must leave the King safe.",
            "The {cooldownTurns}-turn recharge is shared by all Bishops on that side.",
        ],
        "details": [],
    },
    {
        "id": "power_of_love",
        "name": "Power of Love",
        "icon": "♥",
        "summary": "After losing a Queen, the King gains Queen mobility for 10 turns.",
        "summaryTemplate": (
            "After losing a Queen, the King gains Queen mobility for {durationTurns} turn(s)."
        ),
        "tunableParameters": [
            _parameter(
                "durationTurns",
                "Queen Mobility Duration",
                "Own turns for which the King's borrowed Queen mobility remains active.",
                10,
                1,
                50,
                "turn",
            ),
        ],
        "detailTemplates": [
            "The King remains subject to check and may never move onto an attacked square.",
            "Losing another Queen refreshes the {durationTurns}-turn duration instead of stacking it.",
            "The empowered King can give check and checkmate normally.",
        ],
        "details": [],
    },
]


VICTORY_MODES: list[dict[str, Any]] = [
    {
        "id": "checkmate",
        "name": "Classic Checkmate",
        "icon": "♚",
        "summary": "Win by checking the enemy King with no legal escape.",
    },
    {
        "id": "king_capture",
        "name": "King Capture",
        "icon": "⚔",
        "summary": "Kings may be captured directly; taking one wins immediately.",
    },
    {
        "id": "timed",
        "name": "Timed Match",
        "icon": "⏱",
        "summary": "Each player has a chess clock. Running out of time loses the game.",
    },
    {
        "id": "point_race",
        "name": "Point Race",
        "icon": "★",
        "summary": "The first player to reach the configured captured-piece score wins.",
    },
    {
        "id": "elimination",
        "name": "Total Elimination",
        "icon": "✖",
        "summary": "Remove every opposing combat piece; uncapturable Diplomats do not count.",
    },
    {
        "id": "royal_score",
        "name": "Royal Score",
        "icon": "♛",
        "summary": "Royal defeat ends play, but the player with the higher score wins.",
    },
    {
        "id": "center_dominion",
        "name": "Center Dominion",
        "icon": "◆",
        "summary": (
            "Hold both center squares assigned to your color through three consecutive "
            "opponent turns. Checkmate also wins."
        ),
    },
    {
        "id": "royal_center",
        "name": "Royal Center",
        "icon": "♔",
        "summary": (
            "Move your King onto any of the four adaptive center squares. "
            "Checkmate also wins."
        ),
    },
    {
        "id": "check_race",
        "name": "Check Race",
        "icon": "!",
        "summary": (
            "Be the first player to check the opposing King the configured number of times. "
            "Checkmate also wins."
        ),
    },
]


POPULAR_PRESETS: list[dict[str, Any]] = [
    {
        "id": "classic",
        "name": "Classic Chass",
        "icon": "♟",
        "summary": "Standard 8x8 chess with checkmate victory.",
        "boardRows": 8,
        "boardCols": 8,
        "formationId": "classic",
        "victory": {"mode": "checkmate"},
        "gambit": {"enabled": False},
    },
    {
        "id": "point_race",
        "name": "Point Race 21",
        "icon": "★",
        "summary": "Capture 21 points of material before your opponent.",
        "boardRows": 8,
        "boardCols": 8,
        "formationId": "classic",
        "victory": {"mode": "point_race", "targetPoints": 21, "kingPoints": 1},
        "gambit": {"enabled": False},
    },
    {
        "id": "king_hunt",
        "name": "King Hunt",
        "icon": "⚔",
        "summary": "Check restrictions are disabled; capture the opposing King to win.",
        "boardRows": 8,
        "boardCols": 8,
        "formationId": "classic",
        "victory": {"mode": "king_capture", "kingPoints": 1},
        "gambit": {"enabled": False},
    },
    {
        "id": "elimination",
        "name": "Total Elimination",
        "icon": "✖",
        "summary": "The last army with a capturable combat piece on the board wins.",
        "boardRows": 8,
        "boardCols": 8,
        "formationId": "classic",
        "victory": {"mode": "elimination"},
        "gambit": {"enabled": False},
    },
    {
        "id": "blitz",
        "name": "Ten Minute Match",
        "icon": "⏱",
        "summary": "Classic checkmate with a ten-minute clock for each player.",
        "boardRows": 8,
        "boardCols": 8,
        "formationId": "classic",
        "victory": {"mode": "timed", "timeSeconds": 600},
        "gambit": {"enabled": False},
    },
    {
        "id": "center_dominion",
        "name": "Center Dominion",
        "icon": "◆",
        "summary": "Hold both marked center squares for three consecutive rounds.",
        "boardRows": 8,
        "boardCols": 8,
        "formationId": "classic",
        "victory": {"mode": "center_dominion", "dominionRounds": 3},
        "gambit": {"enabled": False},
    },
    {
        "id": "royal_center",
        "name": "Royal Center",
        "icon": "♔",
        "summary": "Race your King to one of the four marked center squares.",
        "boardRows": 8,
        "boardCols": 8,
        "formationId": "classic",
        "victory": {"mode": "royal_center"},
        "gambit": {"enabled": False},
    },
    {
        "id": "check_race",
        "name": "Three-Check Race",
        "icon": "!",
        "summary": "Win by checking the opposing King three times.",
        "boardRows": 8,
        "boardCols": 8,
        "formationId": "classic",
        "victory": {"mode": "check_race", "checkTarget": 3},
        "gambit": {"enabled": False},
    },
    {
        "id": "gambit",
        "name": "Chass Gambit",
        "icon": "⚑",
        "summary": "Secretly build an army worth up to a maximum of 39 points before reveal.",
        "boardRows": 8,
        "boardCols": 8,
        "formationId": "classic",
        "victory": {"mode": "checkmate"},
        "customRules": {"affinityEnabled": True, "commandPointCap": 3},
        "gambit": {"enabled": True, "draftEnabled": False},
    },
    {
        "id": "draft_gambit",
        "name": "Draft Gambit",
        "icon": "◈",
        "summary": (
            "Begin with one King each, alternate picks from a shared pool, then privately "
            "deploy the armies."
        ),
        "boardRows": 8,
        "boardCols": 8,
        "formationId": "classic",
        "victory": {"mode": "checkmate"},
        "customRules": {"affinityEnabled": True, "commandPointCap": 3},
        "gambit": {"enabled": True, "draftEnabled": True},
    },
]


FORMATION_PRESETS: list[dict[str, Any]] = [
    {
        "id": "no_pawns",
        "name": "No Pawns",
        "icon": "♜",
        "summary": "Classic armies without Pawns, opening every file immediately.",
        "defaultVictory": "checkmate",
        "disabledAbilities": {
            "kamikaze": "Kamikaze requires Pawns.",
        },
    },
    {
        "id": "pawn_race",
        "name": "Pawn Race",
        "icon": "♟",
        "summary": "Kings and Pawns only, with promotion deciding the attack.",
        "defaultVictory": "checkmate",
        "disabledAbilities": {
            "getaway": "Getaway requires a Queen.",
            "episcopal": "Episcopal requires a Bishop.",
            "power_of_love": "Power of Love requires a Queen.",
        },
    },
    {
        "id": "knight_skirmish",
        "name": "Knight Skirmish",
        "icon": "♞",
        "summary": "A compact 6x6 duel with two Knights and one King per side.",
        "defaultVictory": "checkmate",
        "disabledAbilities": {
            "getaway": "Getaway requires a Queen.",
            "kamikaze": "Kamikaze requires Pawns.",
            "episcopal": "Episcopal requires a Bishop.",
            "power_of_love": "Power of Love requires a Queen.",
        },
    },
    {
        "id": "horde",
        "name": "Horde",
        "icon": "⚑",
        "summary": "A King-led Pawn horde faces a complete classic army.",
        "defaultVictory": "elimination",
        "disabledVictoryModes": {
            "checkmate": "Horde is decided by army elimination, not checkmate.",
            "timed": "The built-in timed rule also uses checkmate and is unavailable for Horde.",
            "royal_score": "Royal Score depends on checkmate and is unavailable for Horde.",
        },
        "disabledAbilities": {
            "getaway": "White begins without a Queen.",
            "episcopal": "White begins without a Bishop.",
            "power_of_love": "White begins without a Queen.",
        },
    },
    {
        "id": "castle_siege",
        "name": "Castle Siege",
        "icon": "▦",
        "summary": "An 8x10 army with four Rooks, two Knights, and ten Pawns per side.",
        "defaultVictory": "checkmate",
        "disabledAbilities": {},
    },
]

for formation in FORMATION_PRESETS:
    formation_rows, formation_cols, formation_pieces = formation_layout(formation["id"])
    formation["boardRows"] = formation_rows
    formation["boardCols"] = formation_cols
    formation["initialLayout"] = formation_pieces
    formation.setdefault("disabledVictoryModes", {})


def catalog_payload() -> dict[str, Any]:
    definitions = build_catalog_piece_definitions()
    pieces = []
    for raw_definition in definitions.values():
        definition, _ = configure_piece_definition(raw_definition)
        attributes = definition.custom_attributes
        pieces.append(
            {
                "type": definition.type,
                "name": definition.display_name,
                "icon": definition.icon,
                "symbols": definition.symbols,
                "points": definition.points,
                "isCustom": definition.is_custom,
                "description": definition.description,
                "movement": definition.movement_summary,
                "rules": attributes.get("rules", []),
                "descriptionTemplate": attributes.get("descriptionTemplate"),
                "movementTemplate": attributes.get("movementTemplate"),
                "ruleTemplates": attributes.get("ruleTemplates", []),
                "tunableParameters": attributes.get("tunableParameters", []),
                "configuredParameters": attributes.get("configuredParameters", []),
                "visualKey": definition.metadata.get("visualKey", definition.type),
            }
        )

    return {
        "schemaVersion": 2,
        "pieces": pieces,
        "specialAbilities": [
            configure_special_ability(ability)[0] for ability in SPECIAL_ABILITIES
        ],
        "victoryModes": deepcopy(VICTORY_MODES),
        "popularModes": deepcopy(POPULAR_PRESETS),
        "formations": deepcopy(FORMATION_PRESETS),
        "limits": {
            "boardMin": 4,
            "boardMax": 16,
            "pointMin": 0,
            "pointMax": 100000,
            "timeSecondsMin": 60,
            "timeSecondsMax": 86400,
        },
        "gambit": {
            "name": "Chass Gambit",
            "icon": "⚑",
            "summary": (
                "A hidden army-building system that can be combined with custom pieces, "
                "board sizes, victory rules, and special abilities."
            ),
            "details": [
                "Each player edits only the configured home rows.",
                "Each army must contain exactly one King and stay within its point limit.",
                "Armies remain hidden until both players lock in.",
                "Optional custom rules can add affinity squares and command powers.",
            ],
            "draftDetails": [
                "Each army begins with its required King already assigned.",
                "Players alternate public selections of the remaining pieces from one shared pool.",
                "A player may lock below the maximum point budget at any time.",
                "After both players lock, each army is arranged privately in its home rows.",
            ],
        },
    }
