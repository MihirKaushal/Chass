from __future__ import annotations

import random
from collections import Counter

from backend.analysis.chass.evaluator import intrinsic_piece_value
from backend.bots.profiles import BotDifficultyProfile
from backend.models import DeploymentPiece, GameState
from backend.rules import RuleEngine
from backend.rules.gambit_rules import DeploymentZoneRule, create_piece
from backend.rules.variant_system import (
    barricade_start_squares,
    significant_center_start_squares,
)


class ChassSetupPlanner:
    """Builds legal bot setup choices without bypassing Gambit rules."""

    def __init__(self, engine: RuleEngine) -> None:
        self.engine = engine

    @staticmethod
    def _available_piece_types(state: GameState) -> set[str]:
        available = set(state.configuration.enabled_piece_types)
        if state.gambit is not None and state.gambit.config.draft_enabled:
            available &= {
                piece_type
                for piece_type, count in state.gambit.config.draft_pool.items()
                if count > 0
            }
        return available

    def choose_abilities(
        self,
        state: GameState,
        color: str,
        profile: BotDifficultyProfile,
        rng: random.Random,
    ) -> tuple[str, ...]:
        config = state.configuration.special_abilities
        pieces = self._available_piece_types(state)
        victory = state.configuration.victory.mode
        scores = {
            "necromancy": 4.2 + (1.5 if victory in {"point_race", "royal_score"} else 0),
            "getaway": 7.0 if "queen" in pieces else 0.2,
            "eye_for_an_eye": 4.8,
            "kamikaze": 5.5 if "pawn" in pieces else 0.2,
            "episcopal": 5.2 if "bishop" in pieces else 0.2,
            "power_of_love": 5.0 if "queen" in pieces else 0.2,
            "scorch": 4.6 + (0.8 if victory in {"center_dominion", "royal_center"} else 0),
        }
        if victory in {"checkmate", "king_capture", "check_race"}:
            scores["getaway"] += 1.2
            scores["episcopal"] += 0.6
        jitter = 1.8 if profile.target_elo <= 500 else 0.25
        ranked = sorted(
            config.allowed,
            key=lambda ability_id: (
                -(scores.get(ability_id, 1.0) + rng.uniform(-jitter, jitter)),
                ability_id,
            ),
        )
        return tuple(ranked[: config.max_per_player])

    @staticmethod
    def _ability_piece_bonus(state: GameState, color: str, piece_type: str) -> float:
        selected = set(state.abilities.selected[color])
        bonus = 0.0
        if piece_type == "pawn" and "kamikaze" in selected:
            bonus += 1.6
        if piece_type == "bishop" and "episcopal" in selected:
            bonus += 1.5
        if piece_type == "queen" and "getaway" in selected:
            bonus += 1.8
        if piece_type == "queen" and "power_of_love" in selected:
            bonus += 1.2
        return bonus

    def _piece_strength(self, state: GameState, color: str, piece_type: str) -> float:
        try:
            piece = create_piece(state, piece_type, color)
            return intrinsic_piece_value(state, piece)
        except (KeyError, ValueError):
            if state.gambit is None:
                return 1.0
            return float(state.gambit.config.piece_points.get(piece_type, 1))

    def choose_draft_action(
        self,
        state: GameState,
        color: str,
        profile: BotDifficultyProfile,
        rng: random.Random,
    ) -> tuple[str, str | None]:
        if state.gambit is None:
            raise ValueError("Draft planning requires a Gambit state.")
        options = self.engine.gambit.shared_draft.options(state, color)
        if not options:
            if self.engine.gambit.shared_draft.can_pass(state, color):
                return "pass", None
            raise ValueError("The bot has no legal draft action.")

        counts = Counter(state.gambit.draft_picks[color])
        jitter = 2.0 if profile.target_elo <= 500 else 0.2

        def score(piece_type: str) -> float:
            strength = self._piece_strength(state, color, piece_type)
            synergy = self._ability_piece_bonus(state, color, piece_type)
            variety = 0.45 * counts.get(piece_type, 0)
            return strength + synergy - variety + rng.uniform(-jitter, jitter)

        return "pick", max(options, key=lambda piece_type: (score(piece_type), piece_type))

    def _army_inventory(
        self,
        state: GameState,
        color: str,
        profile: BotDifficultyProfile,
        rng: random.Random,
    ) -> list[str]:
        if state.gambit is None:
            raise ValueError("Deployment planning requires a Gambit state.")
        gambit = state.gambit
        if gambit.config.draft_enabled:
            return list(gambit.draft_picks[color])

        inventory = ["king"]
        counts = Counter(inventory)
        spent = gambit.config.piece_points.get("king", 0)
        if spent > gambit.config.budget:
            raise ValueError("The bot cannot afford its required King.")

        while len(inventory) < gambit.config.max_pieces:
            options = []
            for piece_type in state.configuration.enabled_piece_types:
                if piece_type in {"king", "barricade"}:
                    continue
                cap = gambit.config.piece_caps.get(piece_type, 0)
                cost = gambit.config.piece_points.get(piece_type)
                if cost is None or counts[piece_type] >= cap:
                    continue
                if spent + cost <= gambit.config.budget:
                    options.append(piece_type)
            if not options:
                break

            jitter = 1.8 if profile.target_elo <= 500 else 0.15

            def score(piece_type: str, noise: float = jitter) -> float:
                strength = self._piece_strength(state, color, piece_type)
                synergy = self._ability_piece_bonus(state, color, piece_type)
                duplicate_cost = counts[piece_type] * 0.4
                return strength + synergy - duplicate_cost + rng.uniform(-noise, noise)

            selected = max(options, key=lambda piece_type: (score(piece_type), piece_type))
            inventory.append(selected)
            counts[selected] += 1
            spent += gambit.config.piece_points[selected]
        return inventory

    @staticmethod
    def _square_score(
        state: GameState,
        color: str,
        piece_type: str,
        row: int,
        col: int,
    ) -> float:
        depth = row if color == "black" else state.board.rows - 1 - row
        center = abs(col - ((state.board.cols - 1) / 2))
        edge = min(col, state.board.cols - 1 - col)
        if piece_type == "king":
            return -(depth * 5.0) - center
        if piece_type in {"pawn", "catapult", "hypnotizer", "elephant"}:
            return (depth * 3.0) - (center * 0.18)
        if piece_type == "rook":
            return -(depth * 1.8) - (edge * 0.5)
        if piece_type in {"queen", "bishop", "knight", "maharani"}:
            return -(depth * 1.2) - (center * 0.2)
        return -(depth * 0.4) - (center * 0.1)

    def choose_deployment(
        self,
        state: GameState,
        color: str,
        profile: BotDifficultyProfile,
        rng: random.Random,
    ) -> tuple[DeploymentPiece, ...]:
        if state.gambit is None:
            raise ValueError("Deployment planning requires a Gambit state.")
        inventory = self._army_inventory(state, color, profile, rng)
        allowed_rows = DeploymentZoneRule.allowed_rows(state, color)
        reserved = set(
            barricade_start_squares(
                state.board.rows,
                state.board.cols,
                state.configuration.barricade_count,
            )
            if "barricade" in state.configuration.enabled_piece_types
            else []
        )
        reserved.update(
            significant_center_start_squares(
                state.board.rows,
                state.board.cols,
                victory_mode=state.configuration.victory.mode,
                affinity_enabled=state.configuration.custom_rules.affinity_enabled,
                affinity_square_count=(
                    state.configuration.custom_rules.affinity_square_count
                ),
            )
        )
        squares = [
            (row, col)
            for row in sorted(allowed_rows)
            for col in range(state.board.cols)
            if (row, col) not in reserved
        ]
        if len(inventory) > len(squares):
            raise ValueError("The bot army does not fit inside its deployment zone.")

        piece_priority = {
            "king": 0,
            "queen": 1,
            "maharani": 1,
            "rook": 2,
            "bishop": 3,
            "knight": 3,
            "cannibal": 4,
            "diplomat": 4,
            "pawn": 5,
            "catapult": 5,
            "hypnotizer": 5,
            "elephant": 5,
        }
        ordered_inventory = sorted(
            enumerate(inventory),
            key=lambda item: (piece_priority.get(item[1], 4), item[0]),
        )
        jitter = 1.4 if profile.target_elo <= 500 else 0.35
        attempts = max(48, min(240, len(squares) * 8))
        for attempt in range(attempts):
            remaining = set(squares)
            candidate: list[DeploymentPiece] = []
            attempt_jitter = jitter * (1 + attempt / attempts)
            for _, piece_type in ordered_inventory:
                ranked_squares = sorted(
                    remaining,
                    key=lambda square: (
                        -(
                            self._square_score(
                                state,
                                color,
                                piece_type,
                                square[0],
                                square[1],
                            )
                            + rng.uniform(-attempt_jitter, attempt_jitter)
                        ),
                        square,
                    ),
                )
                row, col = ranked_squares[0]
                remaining.remove((row, col))
                candidate.append(DeploymentPiece(row=row, col=col, type=piece_type))

            trial = state.clone()
            assert trial.gambit is not None
            trial.gambit.deployments[color] = candidate
            if self.engine.gambit.setup_issues(trial, color, require_complete=True):
                continue
            if self.engine.gambit.opening_safety.is_legal(trial, self.engine):
                return tuple(candidate)
        raise ValueError("The bot could not construct a legal hidden army for this opening.")
