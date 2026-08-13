from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.models import MovePattern, PieceDefinition

STANDARD_PIECE_TYPES = ("pawn", "knight", "bishop", "rook", "queen", "king")
CUSTOM_PIECE_TYPES = ("maharani", "catapult", "barricade", "hypnotizer", "diplomat")
CLASSIC_BACK_RANK = ("rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook")


def classic_layout(rows: int = 8, cols: int = 8) -> list[dict[str, Any]]:
    if rows < 4 or cols < 8:
        king_col = cols // 2
        return [
            {"row": 0, "col": king_col, "type": "king", "color": "black"},
            {"row": rows - 1, "col": king_col, "type": "king", "color": "white"},
        ]
    start_col = (cols - len(CLASSIC_BACK_RANK)) // 2
    placements: list[dict[str, Any]] = []
    for index, piece_type in enumerate(CLASSIC_BACK_RANK):
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
        return 8, 8, [
            piece for piece in classic_layout() if piece["type"] in {"pawn", "king"}
        ]
    if formation_id == "knight_skirmish":
        return 6, 6, [
            {"row": 0, "col": 2, "type": "king", "color": "black"},
            {"row": 1, "col": 1, "type": "knight", "color": "black"},
            {"row": 1, "col": 4, "type": "knight", "color": "black"},
            {"row": 5, "col": 3, "type": "king", "color": "white"},
            {"row": 4, "col": 1, "type": "knight", "color": "white"},
            {"row": 4, "col": 4, "type": "knight", "color": "white"},
        ]
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
                placements.append(
                    {"row": back_row, "col": col, "type": "rook", "color": color}
                )
                placements.append(
                    {"row": pawn_row, "col": col, "type": "pawn", "color": color}
                )
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
            description="A heavy line piece that controls ranks and files.",
            movement_summary="Moves any number of clear squares horizontally or vertically.",
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
                "rules": ["Queen movement", "Knight movement", "May cross one blocker"],
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
                "rules": [
                    "Projectile over 1 square: recover for 2 own turns",
                    "Projectile over 2 squares: recover for 4 own turns",
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
                "It cannot capture or be captured."
            ),
            points=0,
            is_custom=True,
            behavior="barricade",
            patterns=[],
            custom_attributes={
                "rules": ["Neutral", "Uncapturable", "Blocks jumps and projectiles"],
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
                "rules": [
                    "One recruitment target",
                    "Kings cannot be recruited",
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
            description=(
                "A protected peacekeeper that temporarily pacifies nearby enemy pieces."
            ),
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
                "rules": [
                    "Uncapturable",
                    "Can pacify any enemy piece, including a King",
                    "Pacifies after 2 contact turns",
                    "Retires after 5 pacifications",
                ],
            },
            metadata={"family": "chass_custom", "visualKey": "diplomat"},
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
        "summary": "Spend earned score to recruit a captured enemy piece, then recharge for nine turns.",
        "cooldownTurns": 9,
        "details": [
            "The recruited piece changes to your color.",
            "Its price is its configured point value and spending lowers your score.",
            "Kings, neutral pieces, and unaffordable pieces cannot be recruited.",
            "Deployment requires an empty square in your home rows and consumes a turn.",
        ],
    },
    {
        "id": "getaway",
        "name": "Getaway",
        "icon": "⇄",
        "summary": "Escape checkmate by swapping the King with a Rook or Queen, then recharge for ten turns.",
        "cooldownTurns": 10,
        "details": [
            "The swap is available only when it produces a legal position.",
            "If no legal partner exists, checkmate ends the game normally.",
            "A successful swap starts a ten-turn cooldown.",
        ],
    },
    {
        "id": "eye_for_an_eye",
        "name": "Eye for an Eye",
        "icon": "⚖",
        "summary": "Trade matching pieces, then wait ten turns before using the ability again.",
        "cooldownTurns": 10,
        "details": [
            "A successful trade consumes the turn and starts a ten-turn cooldown.",
            "Kings and neutral pieces cannot be selected.",
            "Neither removal awards score and it cannot be used while in check.",
        ],
    },
    {
        "id": "kamikaze",
        "name": "Kamikaze",
        "icon": "✹",
        "summary": "A final-rank Pawn may detonate instead of promoting.",
        "details": [
            "The Pawn is sacrificed and enemies up to two horizontal squares away are removed.",
            "A Barricade stops the blast from continuing past it.",
            "An enemy King in range causes an immediate ability victory.",
        ],
    },
    {
        "id": "episcopal",
        "name": "Episcopal",
        "icon": "✝",
        "summary": "Every six turns, shift a Bishop one square onto the opposite color.",
        "cooldownTurns": 6,
        "details": [
            "The shift is horizontal or vertical and may capture an enemy on its destination.",
            "It consumes the turn and must leave the King safe.",
            "The six-turn recharge is shared by all Bishops on that side.",
        ],
    },
    {
        "id": "power_of_love",
        "name": "Power of Love",
        "icon": "♥",
        "summary": "After losing a Queen, the King gains Queen mobility for ten turns.",
        "details": [
            "The King remains subject to check and may never move onto an attacked square.",
            "Losing another Queen refreshes the duration instead of stacking it.",
            "The empowered King can give check and checkmate normally.",
        ],
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
        "summary": "Checks are warnings, but the King must actually be captured.",
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
        "id": "gambit",
        "name": "Chass Gambit",
        "icon": "⚑",
        "summary": "Secretly spend exactly 39 points to build an army before reveal.",
        "boardRows": 8,
        "boardCols": 8,
        "formationId": "classic",
        "victory": {"mode": "checkmate"},
        "gambit": {"enabled": True},
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
            "getaway": "Getaway requires a Rook or Queen.",
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
            "getaway": "Getaway requires a Rook or Queen.",
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
            "getaway": "White begins without a Rook or Queen.",
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
    for definition in definitions.values():
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
                "rules": definition.custom_attributes.get("rules", []),
                "visualKey": definition.metadata.get("visualKey", definition.type),
            }
        )

    return {
        "schemaVersion": 2,
        "pieces": pieces,
        "specialAbilities": deepcopy(SPECIAL_ABILITIES),
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
                "Holding both affinity squares of your color earns command points.",
                "Command points buy Reinforce, Evolve, and Stronghold actions.",
            ],
        },
    }
