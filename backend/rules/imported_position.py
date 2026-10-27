"""Validated midgame setup, separate from new-game Customizer restrictions."""

from collections import Counter

from backend.models import Board, GameConfiguration, GameState, Piece
from backend.models.domain import ImportedPosition

STANDARD_TYPES = ("pawn", "knight", "bishop", "rook", "queen", "king")


class ImportedPositionRules:
    def build(self, position, engine, definitions, game_id="scanner-validation"):
        setup = ImportedPosition.model_validate(
            position.model_dump(include=set(ImportedPosition.model_fields))
        )
        definitions = {kind: definitions[kind].model_copy(deep=True) for kind in STANDARD_TYPES}
        grid = [[None] * 8 for _ in range(8)]
        placements, issues = [], []

        def issue(message, squares=(), field="board"):
            issues.append(
                {
                    "message": message,
                    "field": field,
                    "squares": [{"row": row, "col": col} for row, col in squares],
                }
            )

        for row, rank in enumerate(setup.board):
            for col, label in enumerate(rank):
                if label is None:
                    continue
                color, kind = label.split("-")
                definition = definitions[kind]
                grid[row][col] = Piece(
                    type=kind,
                    name=definition.display_name,
                    color=color,
                    points=definition.points,
                    has_moved=not (kind == "pawn" and row == (6 if color == "white" else 1)),
                )
                placements.append({"row": row, "col": col, "type": kind, "color": color})
                if kind == "pawn" and row in {0, 7}:
                    issue(
                        "A midgame Pawn cannot be on the first or last rank. Correct or promote it.",
                        [(row, col)],
                    )

        for color in ("white", "black"):
            army = [item for item in placements if item["color"] == color]
            counts = Counter(item["type"] for item in army)
            squares = [(item["row"], item["col"]) for item in army]
            if counts["king"] != 1:
                issue(
                    f"{color.title()} must have exactly one King.",
                    [(item["row"], item["col"]) for item in army if item["type"] == "king"],
                )
            if len(army) > 16 or counts["pawn"] > 8:
                issue(
                    f"{color.title()} has more pieces or Pawns than classic chess permits.", squares
                )
            bishop_colors = Counter(
                (item["row"] + item["col"]) % 2 for item in army if item["type"] == "bishop"
            )
            promotions = sum(
                max(0, counts[kind] - limit)
                for kind, limit in (("queen", 1), ("rook", 2), ("knight", 2))
            )
            promotions += sum(max(0, count - 1) for count in bishop_colors.values())
            if promotions > 8 - counts["pawn"]:
                issue(
                    f"{color.title()} has too much promoted material for the remaining Pawns.",
                    squares,
                )
            home = 7 if color == "white" else 0
            for side, col in (("king", 7), ("queen", 0)):
                if not getattr(setup.castling_rights, f"{color}_{side}"):
                    continue
                king, rook = grid[home][4], grid[home][col]
                if not (
                    king
                    and king.type == "king"
                    and king.color == color
                    and rook
                    and rook.type == "rook"
                    and rook.color == color
                ):
                    issue(
                        f"{color.title()} {side}side castling requires its King and Rook on their home squares.",
                        [(home, 4), (home, col)],
                        "castlingRights",
                    )
                else:
                    king.has_moved = rook.has_moved = False

        if setup.en_passant:
            row, col = 8 - int(setup.en_passant[1]), ord(setup.en_passant[0]) - ord("a")
            white_turn = setup.current_player == "white"
            victim_row, origin_row = (3, 1) if white_turn else (4, 6)
            victim = grid[victim_row][col]
            if (
                row != (2 if white_turn else 5)
                or grid[row][col] is not None
                or grid[origin_row][col] is not None
                or victim is None
                or victim.type != "pawn"
                or victim.color == setup.current_player
            ):
                issue(
                    "En passant must match the opponent's immediately preceding two-square Pawn move.",
                    [(row, col), (victim_row, col), (origin_row, col)],
                    "enPassant",
                )
            if setup.halfmove_clock != 0:
                issue(
                    "The halfmove clock must be 0 after an en passant setup's Pawn move.",
                    field="halfmoveClock",
                )

        state = GameState(
            id=game_id,
            board=Board(rows=8, cols=8, grid=grid),
            current_player=setup.current_player,
            rules=engine.default_rule_settings(),
            piece_definitions=definitions,
            imported_position=setup,
            configuration=GameConfiguration(
                preset_id="scanned-position",
                formation_id="custom",
                initial_layout=placements,
                enabled_piece_types=list(STANDARD_TYPES),
                barricade_count=0,
            ),
        )
        state.classic.halfmove_clock = setup.halfmove_clock
        if not issues:
            previous_player = "black" if setup.current_player == "white" else "white"
            if engine.is_king_in_check(state, previous_player):
                king = engine.find_king(state, previous_player)
                issue(
                    "The player who just moved cannot have left their King in check. Check the board or whose turn it is.",
                    [king],
                    "currentPlayer",
                )
            else:
                engine.evaluate_state(state)
                if state.phase == "finished":
                    issue(
                        f"This position is already finished: {state.result.description if state.result else state.game_status}"
                    )
        return state, issues
