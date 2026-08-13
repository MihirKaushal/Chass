from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.models import (
    Board,
    DeploymentPiece,
    GambitState,
    GameState,
    MoveRecord,
    Piece,
)
from backend.rules.base import ValidationResult
from backend.rules.builtin_rules import opposing_color
from backend.rules.variant_system import barricade_start_squares


@dataclass(frozen=True)
class GambitRuleDescriptor:
    id: str
    name: str
    description: str
    tier: str = "gambit"
    can_disable: bool = False


class PointBudgetRule:
    descriptor = GambitRuleDescriptor(
        id="gambit_point_budget",
        name="Point War Chest",
        description="Each army obeys the configured budget and locks only after spending it all.",
    )

    def issues(
        self,
        state: GameState,
        pieces: list[DeploymentPiece],
        *,
        require_complete: bool = False,
    ) -> list[str]:
        gambit = _require_gambit(state)
        unknown = sorted({piece.type for piece in pieces} - gambit.config.piece_points.keys())
        if unknown:
            return [f"Unsupported deployment piece: {unknown[0]}"]

        spent = sum(gambit.config.piece_points[piece.type] for piece in pieces)
        if spent > gambit.config.budget:
            return [f"Army costs {spent} points; the limit is {gambit.config.budget}."]
        if require_complete and gambit.config.require_exact_budget and spent != gambit.config.budget:
            return [
                f"Army must spend all {gambit.config.budget} points; {gambit.config.budget - spent} remain."
            ]
        return []


class DeploymentZoneRule:
    descriptor = GambitRuleDescriptor(
        id="gambit_deployment_zone",
        name="Home Rank Deployment",
        description="Players may arrange pieces only on their configured home ranks.",
    )

    @staticmethod
    def allowed_rows(state: GameState, color: str, row_count: int | None = None) -> set[int]:
        gambit = _require_gambit(state)
        count = min(
            state.board.rows,
            row_count if row_count is not None else gambit.config.setup_rows,
        )
        if color == "white":
            return set(range(state.board.rows - count, state.board.rows))
        return set(range(count))

    def issues(
        self,
        state: GameState,
        color: str,
        pieces: list[DeploymentPiece],
    ) -> list[str]:
        rows = self.allowed_rows(state, color)
        occupied: set[tuple[int, int]] = set()
        reserved_barricades = set(
            barricade_start_squares(
                state.board.rows,
                state.board.cols,
                state.configuration.barricade_count,
            )
            if "barricade" in state.configuration.enabled_piece_types
            else []
        )
        for piece in pieces:
            if piece.row not in rows:
                return ["Pieces must stay inside your configured home ranks."]
            if not (0 <= piece.col < state.board.cols):
                return ["Deployment square is outside the board."]
            square = (piece.row, piece.col)
            if square in reserved_barricades:
                return ["Starting Barricade squares are reserved."]
            if square in occupied:
                return ["Only one piece can occupy a deployment square."]
            occupied.add(square)
        return []


class PieceLimitRule:
    descriptor = GambitRuleDescriptor(
        id="gambit_piece_limits",
        name="Army Composition Limits",
        description=(
            "Armies contain at most 16 pieces, exactly one king, and configured limits "
            "for every piece type."
        ),
    )

    def issues(
        self,
        state: GameState,
        pieces: list[DeploymentPiece],
        *,
        require_complete: bool,
    ) -> list[str]:
        gambit = _require_gambit(state)
        issues: list[str] = []
        counts = Counter(piece.type for piece in pieces)

        if len(pieces) > gambit.config.max_pieces:
            issues.append(f"Army may contain at most {gambit.config.max_pieces} pieces.")

        for piece_type, count in counts.items():
            cap = gambit.config.piece_caps.get(piece_type)
            if cap is None:
                issues.append(f"Unsupported deployment piece: {piece_type}")
            elif count > cap:
                issues.append(
                    f"Army may contain at most {cap} {piece_type}{'' if cap == 1 else 's'}."
                )

        king_count = counts.get("king", 0)
        if king_count > 1 or (require_complete and king_count != 1):
            issues.append("Army must contain exactly one King.")
        return issues


class HiddenDeploymentRule:
    descriptor = GambitRuleDescriptor(
        id="gambit_hidden_deployment",
        name="Hidden Deployment",
        description="Opponent armies remain private until both legal setups are locked in.",
    )

    def validate_edit(
        self,
        state: GameState,
        color: str,
        *,
        mode: str,
        room_ready: bool,
    ) -> ValidationResult:
        gambit = _require_gambit(state)
        if state.phase != "deployment":
            return ValidationResult(False, "Deployment is not active right now.")
        if mode == "online" and not room_ready:
            return ValidationResult(False, "Waiting for both player seats before deployment.")
        if mode == "local" and color != gambit.active_deployment_color:
            return ValidationResult(False, "Complete the private handoff before editing this army.")
        if gambit.deployment_ready[color]:
            return ValidationResult(False, "This army is locked in.")
        return ValidationResult(True)


class OpeningSafetyRule:
    descriptor = GambitRuleDescriptor(
        id="gambit_opening_safety",
        name="Legal Opening Position",
        description="Neither king may begin in check and both armies must have a legal move.",
    )

    def is_legal(self, state: GameState, helper) -> bool:
        trial = state.clone()
        trial.board = build_deployment_board(trial)
        trial.phase = "play"
        trial.current_player = "white"
        trial.game_status = "active"
        trial.winner = None

        if helper.is_king_in_check(trial, "white"):
            return False
        if helper.is_king_in_check(trial, "black"):
            return False
        if not helper.get_valid_moves_for_color(trial, "white"):
            return False
        return bool(helper.get_valid_moves_for_color(trial, "black"))


class AffinityControlRule:
    descriptor = GambitRuleDescriptor(
        id="gambit_affinity_control",
        name="Center Affinity",
        description=(
            "Hold both center squares of your color through the opponent's turn to gain "
            "one command point, up to the configured cap."
        ),
    )

    @staticmethod
    def controls(state: GameState, color: str) -> bool:
        gambit = _require_gambit(state)
        if not gambit.config.affinity_enabled:
            return False
        for square in gambit.config.affinity_squares[color]:
            piece = state.board.grid[square.row][square.col]
            if piece is None or piece.color != color:
                return False
        return True

    def complete_turn(self, state: GameState, acting_color: str) -> None:
        gambit = _require_gambit(state)
        if not gambit.config.affinity_enabled:
            state.current_player = opposing_color(acting_color)
            return
        gambit.affinity_primed[acting_color] = self.controls(state, acting_color)

        next_color = opposing_color(acting_color)
        state.current_player = next_color
        if gambit.affinity_primed[next_color] and self.controls(state, next_color):
            current = gambit.command_points[next_color]
            gambit.command_points[next_color] = min(
                gambit.config.command_point_cap,
                current + 1,
            )
        gambit.affinity_primed[next_color] = False


class CommandPointRule:
    descriptor = GambitRuleDescriptor(
        id="gambit_command_points",
        name="Command Points",
        description="Command powers spend earned points and consume the player's full turn.",
    )

    def validate(self, state: GameState, color: str, power: str) -> ValidationResult:
        gambit = _require_gambit(state)
        if state.phase != "play":
            return ValidationResult(False, "Command powers are available only during play.")
        if state.current_player != color:
            return ValidationResult(False, f"It is {state.current_player}'s turn.")
        cost = gambit.config.power_costs[power]
        if gambit.command_points[color] < cost:
            return ValidationResult(False, f"{power.title()} requires {cost} command points.")
        used = gambit.power_usage[color].get(power, 0)
        cap = gambit.config.power_usage_caps[power]
        if used >= cap:
            return ValidationResult(False, f"{power.title()} has reached its game limit.")
        return ValidationResult(True)

    @staticmethod
    def spend(state: GameState, color: str, power: str) -> None:
        gambit = _require_gambit(state)
        gambit.command_points[color] -= gambit.config.power_costs[power]
        gambit.power_usage[color][power] = gambit.power_usage[color].get(power, 0) + 1


class GambitPowerRule:
    power_id: str
    piece_type: str
    descriptor: GambitRuleDescriptor

    def candidate_targets(self, state: GameState, color: str) -> list[tuple[int, int]]:
        raise NotImplementedError

    def apply_to_board(
        self,
        state: GameState,
        color: str,
        row: int,
        col: int,
        evolve_to: str | None,
    ) -> str:
        raise NotImplementedError

    def target_is_legal(
        self,
        state: GameState,
        color: str,
        row: int,
        col: int,
        evolve_to: str | None,
        helper,
    ) -> bool:
        if (row, col) not in self.candidate_targets(state, color):
            return False
        trial = state.clone()
        try:
            self.apply_to_board(trial, color, row, col, evolve_to)
        except ValueError:
            return False
        return not helper.is_king_in_check(trial, color)


class PawnReinforcementRule(GambitPowerRule):
    power_id = "reinforce"
    piece_type = "pawn"
    descriptor = GambitRuleDescriptor(
        id="gambit_pawn_reinforcement",
        name="Reinforce",
        description="Spend 1 command point and a turn to add a pawn on an empty home square.",
    )

    def candidate_targets(self, state: GameState, color: str) -> list[tuple[int, int]]:
        rows = DeploymentZoneRule.allowed_rows(state, color)
        return [
            (row, col)
            for row in sorted(rows)
            for col in range(state.board.cols)
            if state.board.grid[row][col] is None
        ]

    def apply_to_board(
        self,
        state: GameState,
        color: str,
        row: int,
        col: int,
        evolve_to: str | None,
    ) -> str:
        standard_start_row = state.board.rows - 2 if color == "white" else 1
        piece = create_piece(state, "pawn", color)
        piece.has_moved = row != standard_start_row
        piece.custom_attributes["gambitOrigin"] = "Reinforce"
        state.board.grid[row][col] = piece
        return f"{color.title()} used Reinforce and deployed a Pawn."


class PawnEvolutionRule(GambitPowerRule):
    power_id = "evolve"
    piece_type = "pawn"
    descriptor = GambitRuleDescriptor(
        id="gambit_pawn_evolution",
        name="Evolve",
        description="Spend 2 command points and a turn to turn a pawn into a knight or bishop.",
    )

    def candidate_targets(self, state: GameState, color: str) -> list[tuple[int, int]]:
        return [
            (row, col)
            for row in range(state.board.rows)
            for col in range(state.board.cols)
            if (piece := state.board.grid[row][col]) is not None
            and piece.color == color
            and piece.type == "pawn"
        ]

    def apply_to_board(
        self,
        state: GameState,
        color: str,
        row: int,
        col: int,
        evolve_to: str | None,
    ) -> str:
        if evolve_to not in {"knight", "bishop"}:
            raise ValueError("Evolve must create a Knight or Bishop.")
        piece = create_piece(state, evolve_to, color)
        piece.has_moved = True
        piece.custom_attributes["gambitOrigin"] = "Evolve"
        state.board.grid[row][col] = piece
        return f"{color.title()} used Evolve and upgraded a Pawn into a {evolve_to.title()}."


class RookStrongholdRule(GambitPowerRule):
    power_id = "stronghold"
    piece_type = "rook"
    descriptor = GambitRuleDescriptor(
        id="gambit_rook_stronghold",
        name="Stronghold",
        description="Spend 3 command points and a turn to add a rook within your first three ranks.",
    )

    def candidate_targets(self, state: GameState, color: str) -> list[tuple[int, int]]:
        rows = DeploymentZoneRule.allowed_rows(state, color, row_count=3)
        return [
            (row, col)
            for row in sorted(rows)
            for col in range(state.board.cols)
            if state.board.grid[row][col] is None
        ]

    def apply_to_board(
        self,
        state: GameState,
        color: str,
        row: int,
        col: int,
        evolve_to: str | None,
    ) -> str:
        piece = create_piece(state, "rook", color)
        piece.has_moved = True
        piece.custom_attributes["gambitOrigin"] = "Stronghold"
        state.board.grid[row][col] = piece
        return f"{color.title()} used Stronghold and deployed a Rook."


class GambitRuleSet:
    generic_opening_error = (
        "The hidden armies do not form a legal opening. Both players must adjust and lock in again."
    )

    def __init__(self) -> None:
        self.point_budget = PointBudgetRule()
        self.deployment_zone = DeploymentZoneRule()
        self.piece_limits = PieceLimitRule()
        self.hidden_deployment = HiddenDeploymentRule()
        self.opening_safety = OpeningSafetyRule()
        self.affinity = AffinityControlRule()
        self.command_points = CommandPointRule()
        self.power_rules: dict[str, GambitPowerRule] = {
            rule.power_id: rule
            for rule in (
                PawnReinforcementRule(),
                PawnEvolutionRule(),
                RookStrongholdRule(),
            )
        }
        self._descriptors = [
            self.hidden_deployment.descriptor,
            self.point_budget.descriptor,
            self.deployment_zone.descriptor,
            self.piece_limits.descriptor,
            self.opening_safety.descriptor,
            self.affinity.descriptor,
            self.command_points.descriptor,
            *(rule.descriptor for rule in self.power_rules.values()),
        ]

    def available_rules(self) -> list[GambitRuleDescriptor]:
        return list(self._descriptors)

    def setup_issues(
        self,
        state: GameState,
        color: str,
        *,
        require_complete: bool,
    ) -> list[str]:
        gambit = _require_gambit(state)
        pieces = gambit.deployments[color]
        issues = [
            *self.deployment_zone.issues(state, color, pieces),
            *self.point_budget.issues(
                state,
                pieces,
                require_complete=require_complete,
            ),
            *self.piece_limits.issues(
                state,
                pieces,
                require_complete=require_complete,
            ),
        ]
        return list(dict.fromkeys(issues))

    def setup_summary(self, state: GameState, color: str) -> dict:
        gambit = _require_gambit(state)
        pieces = gambit.deployments[color]
        counts = Counter(piece.type for piece in pieces)
        spent = sum(gambit.config.piece_points.get(piece.type, 0) for piece in pieces)
        issues = self.setup_issues(state, color, require_complete=True)
        return {
            "pointsSpent": spent,
            "pointsRemaining": max(0, gambit.config.budget - spent),
            "pieceCount": len(pieces),
            "counts": dict(counts),
            "canReady": not issues,
            "issues": issues,
        }

    def update_deployment(
        self,
        state: GameState,
        color: str,
        *,
        mode: str,
        room_ready: bool,
        action: str,
        row: int | None,
        col: int | None,
        piece_type: str | None,
    ) -> GameState:
        validation = self.hidden_deployment.validate_edit(
            state,
            color,
            mode=mode,
            room_ready=room_ready,
        )
        if not validation.is_valid:
            raise ValueError(validation.reason)

        next_state = state.clone()
        gambit = _require_gambit(next_state)
        current = gambit.deployments[color]

        if action == "undo":
            if not gambit.deployment_undo[color]:
                raise ValueError("There is no deployment change to undo.")
            gambit.deployments[color] = gambit.deployment_undo[color].pop()
            gambit.deployment_versions[color] += 1
            gambit.setup_message = None
            return next_state

        snapshot = [piece.model_copy(deep=True) for piece in current]
        candidate = [piece.model_copy(deep=True) for piece in current]

        if action == "clear":
            if not candidate:
                raise ValueError("This deployment is already empty.")
            candidate = []
        elif action in {"place", "remove"}:
            if row is None or col is None:
                raise ValueError("Choose a deployment square.")
            existing = next(
                (piece for piece in candidate if piece.row == row and piece.col == col),
                None,
            )
            candidate = [
                piece for piece in candidate if not (piece.row == row and piece.col == col)
            ]
            if action == "place":
                if not piece_type:
                    raise ValueError("Choose a piece for this square.")
                candidate.append(DeploymentPiece(row=row, col=col, type=piece_type))
            elif existing is None:
                raise ValueError("There is no piece on that deployment square.")
        else:
            raise ValueError("Unsupported deployment action.")

        issues = self.setup_issues_for_candidate(next_state, color, candidate)
        if issues:
            raise ValueError(issues[0])

        gambit.deployment_undo[color].append(snapshot)
        gambit.deployment_undo[color] = gambit.deployment_undo[color][-40:]
        gambit.deployments[color] = candidate
        gambit.deployment_versions[color] += 1
        gambit.setup_message = None
        return next_state

    def setup_issues_for_candidate(
        self,
        state: GameState,
        color: str,
        candidate: list[DeploymentPiece],
    ) -> list[str]:
        return [
            *self.deployment_zone.issues(state, color, candidate),
            *self.point_budget.issues(state, candidate),
            *self.piece_limits.issues(state, candidate, require_complete=False),
        ]

    def mark_ready(self, state: GameState, color: str, *, mode: str, helper) -> GameState:
        if state.phase != "deployment":
            raise ValueError("Deployment is not active right now.")
        gambit = _require_gambit(state)
        if mode == "local" and color != gambit.active_deployment_color:
            raise ValueError("Complete the private handoff before locking this army.")
        if gambit.deployment_ready[color]:
            raise ValueError("This army is already locked in.")

        issues = self.setup_issues(state, color, require_complete=True)
        if issues:
            raise ValueError(issues[0])

        next_state = state.clone()
        next_gambit = _require_gambit(next_state)
        next_gambit.deployment_ready[color] = True
        next_gambit.deployment_versions[color] += 1
        next_gambit.setup_message = None

        if mode == "local" and color == "white":
            next_gambit.active_deployment_color = "black"
            next_state.phase = "handoff"
            return next_state

        if not all(next_gambit.deployment_ready.values()):
            return next_state

        if not self.opening_safety.is_legal(next_state, helper):
            next_gambit.deployment_ready = {"white": False, "black": False}
            next_gambit.setup_message = self.generic_opening_error
            if mode == "local":
                next_gambit.active_deployment_color = "white"
                next_state.phase = "handoff"
            else:
                next_state.phase = "deployment"
            return next_state

        next_state.board = build_deployment_board(next_state)
        next_state.current_player = "white"
        next_state.phase = "play"
        next_state.game_status = "active"
        next_state.winner = None
        if next_state.clock is not None:
            next_state.clock.active_color = "white"
            next_state.clock.turn_started_at = datetime.now(timezone.utc)
        next_gambit.deployment_undo = {"white": [], "black": []}
        return next_state

    def complete_handoff(self, state: GameState, *, mode: str) -> GameState:
        if mode != "local" or state.phase != "handoff":
            raise ValueError("A private handoff is not waiting right now.")
        next_state = state.clone()
        next_state.phase = "deployment"
        return next_state

    def visible_deployment(
        self,
        state: GameState,
        viewer_color: str | None,
        *,
        mode: str,
    ) -> tuple[str | None, list[DeploymentPiece]]:
        gambit = _require_gambit(state)
        if state.phase == "handoff":
            return None, []
        color = viewer_color if mode == "online" else gambit.active_deployment_color
        if color not in {"white", "black"}:
            return None, []
        return color, [piece.model_copy(deep=True) for piece in gambit.deployments[color]]

    def complete_turn(self, state: GameState, acting_color: str) -> None:
        self.affinity.complete_turn(state, acting_color)

    def affinity_control(self, state: GameState) -> dict[str, bool]:
        return {
            color: self.affinity.controls(state, color)
            for color in ("white", "black")
        }

    def legal_power_targets(self, state: GameState, color: str, helper) -> dict[str, list[dict]]:
        targets: dict[str, list[dict]] = {}
        for power, rule in self.power_rules.items():
            command_validation = self.command_points.validate(state, color, power)
            if not command_validation.is_valid:
                targets[power] = []
                continue
            legal: list[dict] = []
            for row, col in rule.candidate_targets(state, color):
                choices = ("knight", "bishop") if power == "evolve" else (None,)
                if any(
                    rule.target_is_legal(state, color, row, col, choice, helper)
                    for choice in choices
                ):
                    legal.append({"row": row, "col": col})
            targets[power] = legal
        return targets

    def has_legal_power(self, state: GameState, color: str, helper) -> bool:
        return any(self.legal_power_targets(state, color, helper).values())

    def apply_power(
        self,
        state: GameState,
        color: str,
        *,
        power: str,
        row: int,
        col: int,
        evolve_to: str | None,
        helper,
    ) -> tuple[GameState, str]:
        rule = self.power_rules.get(power)
        if rule is None:
            raise ValueError("Unknown command power.")
        command_validation = self.command_points.validate(state, color, power)
        if not command_validation.is_valid:
            raise ValueError(command_validation.reason)
        if not rule.target_is_legal(state, color, row, col, evolve_to, helper):
            raise ValueError("That command action would not leave your King safe.")

        next_state = state.clone()
        explanation = rule.apply_to_board(next_state, color, row, col, evolve_to)
        self.command_points.spend(next_state, color, power)
        next_gambit = _require_gambit(next_state)
        next_gambit.last_power_explanation = explanation
        next_state.history.append(
            MoveRecord(
                move_number=len(next_state.history) + 1,
                player=color,
                piece=rule.piece_type,
                from_row=row,
                from_col=col,
                to_row=row,
                to_col=col,
                captures=[],
                explanation=explanation,
                action_type=power,
            )
        )
        return next_state, explanation


def _require_gambit(state: GameState) -> GambitState:
    if state.variant != "gambit" or state.gambit is None:
        raise ValueError("This action is available only in Chass Gambit.")
    return state.gambit


def create_piece(state: GameState, piece_type: str, color: str) -> Piece:
    definition = state.piece_definitions.get(piece_type)
    if definition is None:
        raise ValueError(f"Unknown piece type: {piece_type}")
    return Piece(
        type=piece_type,
        name=definition.display_name,
        color=color,
        points=definition.points,
        has_moved=False,
        is_custom=definition.is_custom,
        custom_attributes=dict(definition.custom_attributes),
    )


def build_deployment_board(state: GameState) -> Board:
    gambit = _require_gambit(state)
    board = Board(
        rows=state.board.rows,
        cols=state.board.cols,
        grid=[[None for _ in range(state.board.cols)] for _ in range(state.board.rows)],
    )
    for color in ("white", "black"):
        for placement in gambit.deployments[color]:
            piece = create_piece(state, placement.type, color)
            if piece.type == "pawn":
                standard_start_row = state.board.rows - 2 if color == "white" else 1
                piece.has_moved = placement.row != standard_start_row
            board.grid[placement.row][placement.col] = piece
    if "barricade" in state.configuration.enabled_piece_types:
        for row, col in barricade_start_squares(
            state.board.rows,
            state.board.cols,
            state.configuration.barricade_count,
        ):
            if board.grid[row][col] is not None:
                raise ValueError(
                    "Starting Barricade squares must remain empty during deployment."
                )
            board.grid[row][col] = create_piece(state, "barricade", "neutral")
    return board


gambit_rules = GambitRuleSet()
