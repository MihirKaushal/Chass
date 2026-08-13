from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from backend.catalog import SPECIAL_ABILITIES
from backend.models import CaptureEvent, GameResult, GameState, MoveRecord, Piece
from backend.rules.movement import in_bounds

ABILITY_ICONS = {ability["id"]: ability["icon"] for ability in SPECIAL_ABILITIES}
ABILITY_COOLDOWN_TURNS = {
    "necromancy": 9,
    "getaway": 10,
    "eye_for_an_eye": 10,
}
FINISHED_STATUSES = {
    "checkmate",
    "stalemate",
    "score_target",
    "king_capture",
    "points",
    "elimination",
    "time",
    "royal_score",
    "draw",
}


def barricade_start_square(rows: int, cols: int) -> tuple[int, int]:
    return barricade_start_squares(rows, cols, 1)[0]


def centered_board_squares(rows: int, cols: int, count: int) -> list[tuple[int, int]]:
    """Return a rotation-balanced cluster on the board's central row or rows."""
    if rows <= 0 or cols <= 0 or count <= 0:
        return []

    center_rows = [rows // 2] if rows % 2 else [rows // 2 - 1, rows // 2]
    candidates = {(row, col) for row in center_rows for col in range(cols)}
    limit = min(count, len(candidates))

    def rotate(square: tuple[int, int]) -> tuple[int, int]:
        return rows - 1 - square[0], cols - 1 - square[1]

    def distance(square: tuple[int, int]) -> int:
        # Doubled coordinates avoid floating-point center calculations.
        return (2 * square[0] - (rows - 1)) ** 2 + (
            2 * square[1] - (cols - 1)
        ) ** 2

    fixed = sorted(square for square in candidates if rotate(square) == square)
    pairs: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for square in candidates:
        partner = rotate(square)
        if partner == square or partner not in candidates:
            continue
        pairs.add(tuple(sorted((square, partner))))
    ordered_pairs = sorted(pairs, key=lambda pair: (distance(pair[0]), pair))

    selected: list[tuple[int, int]] = []
    if limit % 2 and fixed:
        selected.append(fixed[0])
    for pair in ordered_pairs:
        remaining = limit - len(selected)
        if remaining <= 0:
            break
        if remaining >= 2:
            selected.extend(pair)
        else:
            # An odd count on an even-height board cannot be perfectly
            # rotationally symmetric, so alternate the unavoidable bias.
            selected.append(pair[(len(selected) // 2) % 2])
    return selected


def barricade_start_squares(rows: int, cols: int, count: int) -> list[tuple[int, int]]:
    return centered_board_squares(rows, cols, count)


def affinity_start_squares(
    rows: int,
    cols: int,
) -> dict[str, list[tuple[int, int]]]:
    if rows % 2:
        line = sorted(centered_board_squares(rows, cols, 4), key=lambda item: item[1])
        return {
            "white": [line[0], line[2]],
            "black": [line[1], line[3]],
        }

    upper_row, lower_row = rows // 2 - 1, rows // 2
    center_cols = sorted(
        col for _, col in centered_board_squares(1, cols, 2)
    )
    left_col, right_col = center_cols
    return {
        "white": [(upper_row, left_col), (lower_row, right_col)],
        "black": [(upper_row, right_col), (lower_row, left_col)],
    }


def opposing_color(color: str) -> str:
    return "black" if color == "white" else "white"


def uses_royal_safety(state: GameState) -> bool:
    return state.configuration.victory.mode in {"checkmate", "timed", "royal_score"}


def direct_king_capture_allowed(state: GameState) -> bool:
    return state.configuration.victory.mode in {
        "king_capture",
        "point_race",
        "elimination",
        "royal_score",
    }


def piece_runtime_active(state: GameState, piece: Piece, key: str) -> bool:
    if piece.color not in {"white", "black"}:
        return False
    try:
        until_turn = int(piece.runtime.get(key, 0))
    except (TypeError, ValueError):
        return False
    return until_turn > state.turn_counts[piece.color]


def ability_cooldown_remaining(state: GameState, color: str, ability_id: str) -> int:
    ready_turn = int(
        state.abilities.runtime[color].get(f"{ability_id}_ready_turn", 0)
    )
    return max(0, ready_turn - state.turn_counts[color])


def ability_is_ready(state: GameState, color: str, ability_id: str) -> bool:
    return ability_cooldown_remaining(state, color, ability_id) == 0


def start_ability_cooldown(state: GameState, color: str, ability_id: str) -> None:
    state.abilities.runtime[color][f"{ability_id}_ready_turn"] = (
        state.turn_counts[color] + ABILITY_COOLDOWN_TURNS[ability_id] + 1
    )
    usage = state.abilities.usage_count[color]
    usage[ability_id] = int(usage.get(ability_id, 0)) + 1


def find_piece(state: GameState, piece_id: str) -> tuple[int, int, Piece] | None:
    for row, board_row in enumerate(state.board.grid):
        for col, piece in enumerate(board_row):
            if piece is not None and piece.piece_id == piece_id:
                return row, col, piece
    return None


def trigger_power_of_love(state: GameState, captures: list[CaptureEvent]) -> None:
    queen_colors = {
        capture.piece.color
        for capture in captures
        if capture.piece.type == "queen" and capture.piece.color in {"white", "black"}
    }
    for color in queen_colors:
        if state.abilities.selected.get(color) != "power_of_love":
            continue
        for row in state.board.grid:
            for piece in row:
                if piece is not None and piece.type == "king" and piece.color == color:
                    piece.runtime["love_until_turn"] = state.turn_counts[color] + 10


def _adjacent_positions(state: GameState, row: int, col: int):
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            target_row, target_col = row + dr, col + dc
            if in_bounds(state.board.rows, state.board.cols, target_row, target_col):
                yield target_row, target_col


def _recruitment_threshold(piece: Piece) -> int:
    points = piece.points if piece.points is not None else 99
    if points <= 3:
        return 3
    if points <= 5:
        return 4
    return 5


def _process_hypnotizer(
    state: GameState,
    row: int,
    col: int,
    hypnotizer: Piece,
    messages: list[str],
) -> None:
    candidates = []
    for target_row, target_col in _adjacent_positions(state, row, col):
        target = state.board.grid[target_row][target_col]
        if (
            target is not None
            and target.color in {"white", "black"}
            and target.color != hypnotizer.color
            and target.type != "king"
        ):
            candidates.append((target_row, target_col, target))

    target_id = str(hypnotizer.runtime.get("recruit_target_id", ""))
    selected = next((item for item in candidates if item[2].piece_id == target_id), None)
    if selected is None:
        if not candidates:
            hypnotizer.runtime.pop("recruit_target_id", None)
            hypnotizer.runtime.pop("recruit_progress", None)
            hypnotizer.runtime.pop("recruit_threshold", None)
            return
        selected = min(
            candidates,
            key=lambda item: (
                item[2].points if item[2].points is not None else 100000,
                item[2].piece_id,
            ),
        )
        hypnotizer.runtime["recruit_target_id"] = selected[2].piece_id
        hypnotizer.runtime["recruit_progress"] = 0

    target_row, target_col, target = selected
    progress = int(hypnotizer.runtime.get("recruit_progress", 0)) + 1
    threshold = _recruitment_threshold(target)
    hypnotizer.runtime["recruit_progress"] = progress
    hypnotizer.runtime["recruit_threshold"] = threshold
    hypnotizer.runtime["recruit_target_name"] = target.name

    if progress < threshold:
        return

    target.color = hypnotizer.color
    target.has_moved = True
    target.runtime.pop("pacified_until_turn", None)
    target.runtime.pop("capture_immune_until_turn", None)
    messages.append(
        f"{hypnotizer.color.title()}'s Hypnotizer recruited {target.name}."
    )
    hypnotizer.runtime.pop("recruit_target_id", None)
    hypnotizer.runtime.pop("recruit_progress", None)
    hypnotizer.runtime.pop("recruit_threshold", None)
    hypnotizer.runtime.pop("recruit_target_name", None)
    state.board.grid[target_row][target_col] = target


def _process_diplomat(
    state: GameState,
    row: int,
    col: int,
    diplomat: Piece,
    messages: list[str],
) -> bool:
    contacts = dict(diplomat.runtime.get("diplomat_contacts", {}))
    adjacent_ids: set[str] = set()
    newly_pacified = 0

    for target_row, target_col in _adjacent_positions(state, row, col):
        target = state.board.grid[target_row][target_col]
        if (
            target is None
            or target.color not in {"white", "black"}
            or target.color == diplomat.color
        ):
            continue
        adjacent_ids.add(target.piece_id)
        progress = int(contacts.get(target.piece_id, 0)) + 1
        contacts[target.piece_id] = progress
        if progress < 2:
            continue

        until_turn = state.turn_counts[target.color] + 5
        if int(target.runtime.get("pacified_until_turn", 0)) <= state.turn_counts[target.color]:
            newly_pacified += 1
            messages.append(
                f"{diplomat.color.title()}'s Diplomat pacified {target.name} for 5 turns."
            )
        target.runtime["pacified_until_turn"] = max(
            int(target.runtime.get("pacified_until_turn", 0)),
            until_turn,
        )
        target.runtime["capture_immune_until_turn"] = max(
            int(target.runtime.get("capture_immune_until_turn", 0)),
            until_turn,
        )
        contacts[target.piece_id] = 0

    diplomat.runtime["diplomat_contacts"] = {
        piece_id: progress
        for piece_id, progress in contacts.items()
        if piece_id in adjacent_ids
    }
    retire_count = int(diplomat.runtime.get("pacifications", 0)) + newly_pacified
    diplomat.runtime["pacifications"] = retire_count
    if retire_count >= 5:
        state.board.grid[row][col] = None
        messages.append(f"{diplomat.color.title()}'s Diplomat retired after five pacifications.")
        return True
    return False


def process_end_of_turn_effects(state: GameState, acting_color: str) -> list[str]:
    messages: list[str] = []
    pieces = [
        (row, col, piece)
        for row, board_row in enumerate(state.board.grid)
        for col, piece in enumerate(board_row)
        if piece is not None and piece.color == acting_color
    ]
    for row, col, piece in pieces:
        current = state.board.grid[row][col]
        if current is None or current.piece_id != piece.piece_id:
            continue
        if piece.type == "hypnotizer":
            _process_hypnotizer(state, row, col, piece, messages)
        elif piece.type == "diplomat":
            _process_diplomat(state, row, col, piece, messages)
    return messages


@dataclass(frozen=True)
class ActionResult:
    state: GameState
    explanation: str


class VariantActionRules:
    def _validate_turn(self, state: GameState, color: str) -> None:
        if state.phase != "play":
            raise ValueError("This action is available only during play.")
        if state.game_status in FINISHED_STATUSES or state.winner is not None:
            raise ValueError("Game is already finished.")
        if state.current_player != color:
            raise ValueError(f"It is {state.current_player}'s turn.")

    @staticmethod
    def _position(payload: dict, name: str) -> tuple[int, int]:
        value = payload.get(name)
        if not isinstance(value, dict):
            raise ValueError(f"Choose a {name} square.")
        try:
            return int(value["row"]), int(value["col"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Choose a valid {name} square.") from error

    @staticmethod
    def _piece_at(state: GameState, position: tuple[int, int]) -> Piece:
        row, col = position
        if not in_bounds(state.board.rows, state.board.cols, row, col):
            raise ValueError("Action square is outside the board.")
        piece = state.board.grid[row][col]
        if piece is None:
            raise ValueError("There is no piece on that square.")
        return piece

    @staticmethod
    def _record(
        state: GameState,
        color: str,
        piece_type: str,
        source: tuple[int, int],
        target: tuple[int, int],
        explanation: str,
        captures: list[CaptureEvent] | None = None,
        action_type: str = "ability",
    ) -> None:
        state.history.append(
            MoveRecord(
                move_number=len(state.history) + 1,
                player=color,
                piece=piece_type,
                from_row=source[0],
                from_col=source[1],
                to_row=target[0],
                to_col=target[1],
                captures=captures or [],
                explanation=explanation,
                action_type=action_type,
            )
        )

    @staticmethod
    def _capture_is_legal(state: GameState, target: Piece) -> bool:
        if target.type in {"barricade", "diplomat"}:
            return False
        if piece_runtime_active(state, target, "capture_immune_until_turn"):
            return False
        return target.type != "king" or direct_king_capture_allowed(state)

    @staticmethod
    def _king_safe(state: GameState, color: str, helper) -> bool:
        return not uses_royal_safety(state) or not helper.is_king_in_check(state, color)

    def _catapult_actions(self, state: GameState, color: str) -> list[dict]:
        actions: list[dict] = []
        direction = -1 if color == "white" else 1
        for row, board_row in enumerate(state.board.grid):
            for col, piece in enumerate(board_row):
                if piece is None or piece.color != color or piece.type != "catapult":
                    continue
                if piece_runtime_active(state, piece, "catapult_ready_turn"):
                    continue
                for lane in (-1, 0, 1):
                    for distance in (2, 3):
                        target_row = row + direction * distance
                        target_col = col + lane * distance
                        if not in_bounds(
                            state.board.rows,
                            state.board.cols,
                            target_row,
                            target_col,
                        ):
                            continue
                        blocked = any(
                            (blocker := state.board.grid[row + direction * step][col + lane * step])
                            is not None
                            and blocker.type == "barricade"
                            for step in range(1, distance)
                        )
                        target = state.board.grid[target_row][target_col]
                        if (
                            blocked
                            or target is None
                            or target.color == color
                            or not self._capture_is_legal(state, target)
                        ):
                            continue
                        actions.append(
                            {
                                "id": f"catapult:{piece.piece_id}:{target_row}:{target_col}",
                                "actionType": "catapult_projectile",
                                "owner": color,
                                "icon": "🎯",
                                "label": f"Fire at {target.name}",
                                "description": (
                                    f"Projectile crosses {distance - 1} square(s), then the "
                                    f"Catapult recovers for {2 if distance == 2 else 4} turns."
                                ),
                                "source": {"row": row, "col": col},
                                "target": {"row": target_row, "col": target_col},
                            }
                        )
        return actions

    def _barricade_actions(self, state: GameState, color: str) -> list[dict]:
        actions: list[dict] = []
        for row, board_row in enumerate(state.board.grid):
            for col, piece in enumerate(board_row):
                if piece is None or piece.type != "barricade":
                    continue
                touching = any(
                    (neighbor := state.board.grid[r][c]) is not None
                    and neighbor.color == color
                    for r, c in _adjacent_positions(state, row, col)
                )
                if not touching:
                    continue
                for target_row, target_col in _adjacent_positions(state, row, col):
                    if state.board.grid[target_row][target_col] is None:
                        actions.append(
                            {
                                "id": f"barricade:{piece.piece_id}:{target_row}:{target_col}",
                                "actionType": "move_barricade",
                                "owner": color,
                                "icon": "🧱",
                                "label": "Move Barricade",
                                "description": "Move the adjacent neutral wall one square.",
                                "source": {"row": row, "col": col},
                                "target": {"row": target_row, "col": target_col},
                            }
                        )
        return actions

    def _getaway_actions(self, state: GameState, color: str, helper) -> list[dict]:
        if (
            state.abilities.selected.get(color) != "getaway"
            or not ability_is_ready(state, color, "getaway")
            or state.game_status != "check"
            or helper.has_any_legal_move(state, color)
        ):
            return []
        king = helper.find_king(state, color)
        if king is None:
            return []
        actions = []
        for row, board_row in enumerate(state.board.grid):
            for col, piece in enumerate(board_row):
                if piece is None or piece.color != color or piece.type not in {"rook", "queen"}:
                    continue
                trial = state.clone()
                trial.board.grid[king[0]][king[1]], trial.board.grid[row][col] = (
                    trial.board.grid[row][col],
                    trial.board.grid[king[0]][king[1]],
                )
                if helper.is_king_in_check(trial, color):
                    continue
                actions.append(
                    {
                        "id": f"getaway:{piece.piece_id}",
                        "actionType": "getaway",
                        "owner": color,
                        "icon": "⇄",
                        "label": f"Getaway with {piece.name}",
                        "description": "Swap out of checkmate, then recharge for ten turns.",
                        "source": {"row": king[0], "col": king[1]},
                        "target": {"row": row, "col": col},
                    }
                )
        return actions

    def _episcopal_actions(self, state: GameState, color: str) -> list[dict]:
        if state.abilities.selected.get(color) != "episcopal":
            return []
        ready_turn = int(state.abilities.runtime[color].get("episcopal_ready_turn", 0))
        if state.turn_counts[color] < ready_turn:
            return []
        actions = []
        for row, board_row in enumerate(state.board.grid):
            for col, piece in enumerate(board_row):
                if piece is None or piece.color != color or piece.type != "bishop":
                    continue
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    target_row, target_col = row + dr, col + dc
                    if not in_bounds(
                        state.board.rows, state.board.cols, target_row, target_col
                    ):
                        continue
                    target = state.board.grid[target_row][target_col]
                    if target is not None and (
                        target.color == color or not self._capture_is_legal(state, target)
                    ):
                        continue
                    actions.append(
                        {
                            "id": f"episcopal:{piece.piece_id}:{target_row}:{target_col}",
                            "actionType": "episcopal",
                            "owner": color,
                            "icon": "✝",
                            "label": "Episcopal Shift",
                            "description": "Shift this Bishop onto the opposite square color.",
                            "source": {"row": row, "col": col},
                            "target": {"row": target_row, "col": target_col},
                        }
                    )
        return actions

    def _eye_actions(self, state: GameState, color: str, helper) -> list[dict]:
        if (
            state.abilities.selected.get(color) != "eye_for_an_eye"
            or not ability_is_ready(state, color, "eye_for_an_eye")
            or helper.is_king_in_check(state, color)
        ):
            return []
        own: dict[str, list[tuple[int, int, Piece]]] = {}
        enemy: dict[str, list[tuple[int, int, Piece]]] = {}
        for row, board_row in enumerate(state.board.grid):
            for col, piece in enumerate(board_row):
                if piece is None or piece.type in {"king", "barricade", "diplomat"}:
                    continue
                collection = own if piece.color == color else enemy
                if piece.color in {"white", "black"}:
                    collection.setdefault(piece.type, []).append((row, col, piece))
        actions = []
        for piece_type in sorted(set(own) & set(enemy)):
            for own_row, own_col, own_piece in own[piece_type]:
                for enemy_row, enemy_col, enemy_piece in enemy[piece_type]:
                    actions.append(
                        {
                            "id": f"eye:{own_piece.piece_id}:{enemy_piece.piece_id}",
                            "actionType": "eye_for_an_eye",
                            "owner": color,
                            "icon": "⚖",
                            "label": f"Trade {own_piece.name}",
                            "description": f"Sacrifice it to remove the enemy {enemy_piece.name}.",
                            "source": {"row": own_row, "col": own_col},
                            "target": {"row": enemy_row, "col": enemy_col},
                        }
                    )
        return actions

    def _necromancy_actions(self, state: GameState, color: str) -> list[dict]:
        if (
            state.abilities.selected.get(color) != "necromancy"
            or not ability_is_ready(state, color, "necromancy")
        ):
            return []
        revived = set(state.abilities.runtime[color].get("revived_piece_ids", []))
        home_rows = (
            set(range(state.board.rows - state.gambit.config.setup_rows, state.board.rows))
            if state.gambit is not None and color == "white"
            else (
                set(range(state.gambit.config.setup_rows))
                if state.gambit is not None
                else (
                    set(range(max(0, state.board.rows - 2), state.board.rows))
                    if color == "white"
                    else set(range(min(2, state.board.rows)))
                )
            )
        )
        empty = [
            (row, col)
            for row in sorted(home_rows)
            for col in range(state.board.cols)
            if state.board.grid[row][col] is None
        ]
        if not empty:
            return []
        actions = []
        for captured in state.captured_pieces.get(color, []):
            cost = captured.points or 0
            if (
                captured.piece_id in revived
                or captured.type in {"king", "barricade"}
                or cost > state.score[color]
            ):
                continue
            for row, col in empty:
                actions.append(
                    {
                        "id": f"necromancy:{captured.piece_id}:{row}:{col}",
                        "actionType": "necromancy",
                        "owner": color,
                        "icon": "☠",
                        "label": f"Recruit {captured.name}",
                        "description": f"Spend {cost} score and deploy it on this home square.",
                        "target": {"row": row, "col": col},
                        "params": {"capturedPieceId": captured.piece_id},
                    }
                )
        return actions

    def available_actions(self, state: GameState, color: str, helper) -> list[dict]:
        if state.phase != "play" or state.current_player != color:
            return []
        actions = [
            *self._catapult_actions(state, color),
            *self._barricade_actions(state, color),
            *self._getaway_actions(state, color, helper),
            *self._episcopal_actions(state, color),
            *self._eye_actions(state, color, helper),
            *self._necromancy_actions(state, color),
        ]
        legal: list[dict] = []
        for action in actions:
            if action["actionType"] == "getaway":
                legal.append(action)
                continue
            trial = state.clone()
            try:
                self._apply(trial, color, action, helper, simulated=True)
            except ValueError:
                continue
            if self._king_safe(trial, color, helper):
                legal.append(action)
        return legal

    def has_legal_action(self, state: GameState, color: str, helper) -> bool:
        return bool(self.available_actions(state, color, helper))

    @staticmethod
    def _match_action(available: list[dict], payload: dict) -> dict:
        action_type = payload.get("actionType")
        source = payload.get("source")
        target = payload.get("target")
        secondary = payload.get("secondary")
        params = payload.get("params") or {}
        for action in available:
            if action["actionType"] != action_type:
                continue
            if action.get("source") != source or action.get("target") != target:
                continue
            if action.get("secondary") != secondary:
                continue
            expected_params = action.get("params") or {}
            if any(params.get(key) != value for key, value in expected_params.items()):
                continue
            return action
        raise ValueError("That special action is not legal in the current position.")

    def apply_action(self, state: GameState, color: str, payload: dict, helper) -> ActionResult:
        self._validate_turn(state, color)
        matched = self._match_action(self.available_actions(state, color, helper), payload)
        next_state = state.clone()
        explanation = self._apply(next_state, color, matched, helper, simulated=False)
        return ActionResult(next_state, explanation)

    def _apply(
        self,
        state: GameState,
        color: str,
        action: dict,
        helper,
        *,
        simulated: bool,
    ) -> str:
        action_type = action["actionType"]
        source = (
            (action["source"]["row"], action["source"]["col"])
            if action.get("source")
            else None
        )
        target = (
            (action["target"]["row"], action["target"]["col"])
            if action.get("target")
            else None
        )
        captures: list[CaptureEvent] = []

        if action_type == "catapult_projectile":
            assert source is not None and target is not None
            catapult = self._piece_at(state, source)
            victim = self._piece_at(state, target)
            state.board.grid[target[0]][target[1]] = None
            distance = abs(target[0] - source[0])
            cooldown = 2 if distance == 2 else 4
            catapult.runtime["catapult_ready_turn"] = state.turn_counts[color] + cooldown + 1
            captures.append(CaptureEvent(row=target[0], col=target[1], piece=victim, reason="Catapult projectile"))
            explanation = f"{color.title()}'s Catapult fired and captured {victim.name}."
            piece_type = "catapult"
        elif action_type == "move_barricade":
            assert source is not None and target is not None
            barricade = self._piece_at(state, source)
            state.board.grid[source[0]][source[1]] = None
            state.board.grid[target[0]][target[1]] = barricade
            barricade.has_moved = True
            explanation = f"{color.title()} repositioned the Barricade."
            piece_type = "barricade"
        elif action_type == "episcopal":
            assert source is not None and target is not None
            bishop = self._piece_at(state, source)
            victim = state.board.grid[target[0]][target[1]]
            state.board.grid[source[0]][source[1]] = None
            state.board.grid[target[0]][target[1]] = bishop
            bishop.has_moved = True
            if victim is not None:
                captures.append(CaptureEvent(row=target[0], col=target[1], piece=victim, reason="Episcopal shift"))
            state.abilities.runtime[color]["episcopal_ready_turn"] = state.turn_counts[color] + 7
            explanation = f"{color.title()} used Episcopal to shift a Bishop."
            piece_type = "bishop"
        elif action_type == "getaway":
            assert source is not None and target is not None
            state.board.grid[source[0]][source[1]], state.board.grid[target[0]][target[1]] = (
                state.board.grid[target[0]][target[1]],
                state.board.grid[source[0]][source[1]],
            )
            start_ability_cooldown(state, color, "getaway")
            state.abilities.used[color] = True
            explanation = f"{color.title()} used Getaway and escaped royal defeat."
            piece_type = "king"
        elif action_type == "eye_for_an_eye":
            assert source is not None and target is not None
            sacrificed = self._piece_at(state, source)
            victim = self._piece_at(state, target)
            state.board.grid[source[0]][source[1]] = None
            state.board.grid[target[0]][target[1]] = None
            start_ability_cooldown(state, color, "eye_for_an_eye")
            state.abilities.used[color] = True
            captures.extend(
                [
                    CaptureEvent(row=target[0], col=target[1], piece=victim, reason="Eye for an Eye"),
                    CaptureEvent(row=source[0], col=source[1], piece=sacrificed, reason="Eye for an Eye sacrifice"),
                ]
            )
            explanation = f"{color.title()} traded {sacrificed.name} for the enemy {victim.name}."
            piece_type = sacrificed.type
        elif action_type == "necromancy":
            assert target is not None
            captured_id = str(action.get("params", {}).get("capturedPieceId", ""))
            captured = next(
                piece
                for piece in state.captured_pieces[color]
                if piece.piece_id == captured_id
            )
            revived = captured.model_copy(deep=True)
            revived.piece_id = str(uuid4())
            revived.color = color
            revived.has_moved = True
            revived.runtime = {"necromancy_origin": captured.piece_id}
            state.board.grid[target[0]][target[1]] = revived
            cost = captured.points or 0
            state.spent_score[color] += cost
            revived_ids = list(state.abilities.runtime[color].get("revived_piece_ids", []))
            revived_ids.append(captured.piece_id)
            state.abilities.runtime[color]["revived_piece_ids"] = revived_ids
            start_ability_cooldown(state, color, "necromancy")
            state.abilities.used[color] = True
            explanation = f"{color.title()} spent {cost} score to recruit {captured.name}."
            piece_type = captured.type
            source = target
        else:
            raise ValueError("Unknown special action.")

        if not self._king_safe(state, color, helper):
            raise ValueError("That action would leave your King in check.")

        if simulated:
            return explanation

        scored_captures = captures
        if action_type == "eye_for_an_eye":
            scored_captures = []
        if captures:
            trigger_power_of_love(state, captures)
        if scored_captures:
            state.captured_pieces[color].extend(
                capture.piece for capture in scored_captures
            )

        self._record(
            state,
            color,
            piece_type,
            source or target or (0, 0),
            target or source or (0, 0),
            explanation,
            captures,
            action_type,
        )
        return explanation


def public_countdowns(state: GameState) -> list[dict]:
    countdowns: list[dict] = []
    for row in state.board.grid:
        for piece in row:
            if piece is None or piece.color not in {"white", "black"}:
                continue
            current = state.turn_counts[piece.color]
            fields = (
                (
                    "catapult_ready_turn",
                    "catapult",
                    "🎯",
                    "Catapult Recovery",
                    "Projectile and movement are unavailable while the Catapult resets.",
                ),
                (
                    "pacified_until_turn",
                    "pacified",
                    "🤝",
                    "Pacified",
                    "This piece cannot move, attack, or be captured.",
                ),
                (
                    "love_until_turn",
                    "power_of_love",
                    "♥",
                    "Power of Love",
                    "The King currently has Queen mobility.",
                ),
            )
            for key, kind, icon, label, description in fields:
                remaining = int(piece.runtime.get(key, 0)) - current
                if remaining > 0:
                    countdowns.append(
                        {
                            "id": f"{kind}:{piece.piece_id}",
                            "owner": piece.color,
                            "kind": kind,
                            "icon": icon,
                            "label": label,
                            "description": description,
                            "remainingTurns": remaining,
                            "pieceId": piece.piece_id,
                            "pieceName": piece.name,
                        }
                    )

            if piece.type == "hypnotizer" and piece.runtime.get("recruit_target_id"):
                remaining = int(piece.runtime.get("recruit_threshold", 0)) - int(
                    piece.runtime.get("recruit_progress", 0)
                )
                if remaining > 0:
                    countdowns.append(
                        {
                            "id": f"recruit:{piece.piece_id}",
                            "owner": piece.color,
                            "kind": "recruitment",
                            "icon": "🌀",
                            "label": "Recruitment Contact",
                            "description": (
                                f"Recruiting {piece.runtime.get('recruit_target_name', 'an enemy')}."
                            ),
                            "remainingTurns": remaining,
                            "pieceId": piece.piece_id,
                            "pieceName": piece.name,
                        }
                    )

            if piece.type == "diplomat":
                contacts = dict(piece.runtime.get("diplomat_contacts", {}))
                for target_id, progress_value in contacts.items():
                    progress = int(progress_value)
                    target_match = find_piece(state, target_id)
                    remaining = 2 - progress
                    if target_match is None or remaining <= 0:
                        continue
                    target = target_match[2]
                    countdowns.append(
                        {
                            "id": f"diplomat-contact:{piece.piece_id}:{target_id}",
                            "owner": piece.color,
                            "kind": "diplomat_contact",
                            "icon": "🤝",
                            "label": "Diplomatic Contact",
                            "description": f"Maintaining contact with {target.name}.",
                            "remainingTurns": remaining,
                            "pieceId": piece.piece_id,
                            "pieceName": piece.name,
                        }
                    )

    for color in ("white", "black"):
        if state.abilities.selected.get(color) == "episcopal":
            ready = int(state.abilities.runtime[color].get("episcopal_ready_turn", 0))
            remaining = ready - state.turn_counts[color]
            if remaining > 0:
                countdowns.append(
                    {
                        "id": f"episcopal:{color}",
                        "owner": color,
                        "kind": "episcopal",
                        "icon": "✝",
                        "label": "Episcopal Recharge",
                        "description": "The Bishop color-shift is recharging.",
                        "remainingTurns": remaining,
                    }
                )
        selected = state.abilities.selected.get(color)
        if selected in ABILITY_COOLDOWN_TURNS:
            remaining = ability_cooldown_remaining(state, color, selected)
            if remaining > 0:
                countdowns.append(
                    {
                        "id": f"ability:{selected}:{color}",
                        "owner": color,
                        "kind": selected,
                        "icon": ABILITY_ICONS[selected],
                        "label": f"{selected.replace('_', ' ').title()} Recharge",
                        "description": "This player ability is recharging.",
                        "remainingTurns": remaining,
                    }
                )
    return sorted(countdowns, key=lambda item: (item["owner"], item["remainingTurns"], item["id"]))


def finish_game(
    state: GameState,
    *,
    status: str,
    reason_code: str,
    trigger: str,
    winner: str | None,
    description: str,
) -> None:
    state.game_status = status
    state.winner = winner
    state.phase = "finished"
    state.result = GameResult(
        reason_code=reason_code,
        description=description,
        trigger=trigger,
        winner=winner,
    )
