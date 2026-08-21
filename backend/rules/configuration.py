from __future__ import annotations

from dataclasses import dataclass, field

from backend.catalog import (
    FORMATION_PRESETS,
    build_catalog_piece_definitions,
    build_default_draft_pool,
    classic_layout,
    normalize_ability_parameters,
    normalize_piece_parameters,
)
from backend.models import PieceDefinition
from backend.models.schemas import CreateGameRequest
from backend.rules.material import INSUFFICIENT_MATERIAL_MESSAGE, StartingMaterialRule
from backend.rules.variant_system import barricade_start_squares, objective_center_squares


@dataclass
class ConfigurationValidation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    disabled_options: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": list(dict.fromkeys(self.errors)),
            "warnings": list(dict.fromkeys(self.warnings)),
            "disabledOptions": self.disabled_options,
        }


def _placement_key(piece: dict) -> tuple[int, int, str, str]:
    return piece["row"], piece["col"], piece["type"], piece["color"]


class ConfigurationRuleEngine:
    def __init__(self) -> None:
        self._pieces = build_catalog_piece_definitions()
        self._formations = {item["id"]: item for item in FORMATION_PRESETS}
        self.material = StartingMaterialRule()

    def validate(
        self,
        request: CreateGameRequest,
        *,
        piece_definitions: dict[str, PieceDefinition] | None = None,
        use_default_layout: bool = True,
    ) -> ConfigurationValidation:
        result = ConfigurationValidation()
        payload = request.configuration
        if payload is None:
            return result

        pieces = piece_definitions or self._pieces

        enabled = set(payload.enabledPieces)
        unknown = sorted(enabled - set(pieces))
        if unknown:
            result.errors.append(f"Unknown piece type: {unknown[0]}.")
        if "king" not in enabled:
            result.errors.append("The King must remain enabled.")

        if any(
            value is not None and (not isinstance(value, int) or value < 0)
            for value in payload.piecePoints.values()
        ):
            result.errors.append("Every piece value must be a whole number of zero or more.")

        for supplied, normalizer in (
            (payload.pieceParameters, normalize_piece_parameters),
            (payload.specialAbilities.parameters, normalize_ability_parameters),
        ):
            try:
                normalizer(supplied, pieces) if normalizer is normalize_piece_parameters else normalizer(supplied)
            except ValueError as error:
                result.errors.append(f"{error}.")

        formation = self._formations.get(payload.formationId)
        if formation is not None:
            result.disabled_options = {
                "victoryModes": dict(formation.get("disabledVictoryModes", {})),
                "abilities": dict(formation.get("disabledAbilities", {})),
            }
            if (request.boardRows, request.boardCols) != (
                formation["boardRows"],
                formation["boardCols"],
            ):
                result.errors.append(
                    f"{formation['name']} uses a {formation['boardRows']}x"
                    f"{formation['boardCols']} board."
                )
            if payload.victory.mode in formation.get("disabledVictoryModes", {}):
                result.errors.append(formation["disabledVictoryModes"][payload.victory.mode])
            if not payload.gambit.enabled:
                expected = sorted((_placement_key(piece) for piece in formation["initialLayout"]))
                actual = sorted(
                    (
                        placement.row,
                        placement.col,
                        placement.type,
                        placement.color,
                    )
                    for placement in payload.initialLayout
                    if placement.type != "barricade"
                )
                if actual != expected:
                    result.errors.append(
                        f"The board no longer matches {formation['name']}. "
                        "Choose Custom before editing its formation."
                    )

        if payload.specialAbilities.enabled:
            if not payload.specialAbilities.allowed:
                result.errors.append("Enable at least one ability for players to choose.")
            unique_abilities = set(payload.specialAbilities.allowed)
            if payload.specialAbilities.maxPerPlayer > len(unique_abilities):
                result.errors.append(
                    "Abilities per player cannot exceed the number of enabled abilities."
                )
            disabled_abilities = result.disabled_options.get("abilities", {})
            for ability in payload.specialAbilities.allowed:
                if ability in disabled_abilities:
                    result.errors.append(disabled_abilities[ability])

        max_barricades = max(1, request.boardCols // 2)
        if "barricade" in enabled:
            if payload.barricadeCount < 1:
                result.errors.append("Enable at least one Barricade or turn the piece off.")
            if payload.barricadeCount > max_barricades:
                result.errors.append(
                    f"This board supports at most {max_barricades} starting Barricades."
                )

        placements = [placement.model_dump() for placement in payload.initialLayout]
        occupied: set[tuple[int, int]] = set()
        supplied_barricades = [
            placement for placement in placements if placement["type"] == "barricade"
        ]
        allowed_barricades = set(
            barricade_start_squares(
                request.boardRows,
                request.boardCols,
                payload.barricadeCount,
            )
        )
        if len(supplied_barricades) > payload.barricadeCount or any(
            (piece["row"], piece["col"]) not in allowed_barricades for piece in supplied_barricades
        ):
            result.errors.append("Starting Barricades must use the reserved central squares.")
        if "barricade" in enabled and any(
            (piece["row"], piece["col"]) in allowed_barricades and piece["type"] != "barricade"
            for piece in placements
        ):
            result.errors.append(
                "Starting Barricade positions must remain empty in the board center."
            )
        pawn_promotion_rows = {"white": 0, "black": request.boardRows - 1}
        for placement in placements:
            square = placement["row"], placement["col"]
            if not (
                0 <= placement["row"] < request.boardRows
                and 0 <= placement["col"] < request.boardCols
            ):
                result.errors.append("Every starting piece must be inside the board.")
            if square in occupied:
                result.errors.append("Only one piece may occupy each starting square.")
            occupied.add(square)
            if placement["type"] not in enabled:
                result.errors.append(f"Starting {placement['type'].title()} is not enabled.")
            if placement["type"] == "barricade" and placement["color"] != "neutral":
                result.errors.append("Barricades must be neutral.")
            if placement["type"] != "barricade" and placement["color"] == "neutral":
                result.errors.append("Only Barricades may be neutral.")
            if (
                placement["type"] == "pawn"
                and placement["row"] == pawn_promotion_rows.get(placement["color"])
            ):
                result.errors.append("Pawns cannot begin on a promotion rank.")

        if not payload.gambit.enabled:
            effective = (
                placements
                if placements or not use_default_layout
                else classic_layout(request.boardRows, request.boardCols)
            )
            for color in ("white", "black"):
                kings = [
                    piece
                    for piece in effective
                    if piece["type"] == "king" and piece["color"] == color
                ]
                if len(kings) != 1:
                    result.errors.append(f"{color.title()} must begin with exactly one King.")
            kings = {
                piece["color"]: (piece["row"], piece["col"])
                for piece in effective
                if piece["type"] == "king" and piece["color"] in {"white", "black"}
            }
            if (
                len(kings) == 2
                and max(
                    abs(kings["white"][0] - kings["black"][0]),
                    abs(kings["white"][1] - kings["black"][1]),
                )
                <= 1
            ):
                result.errors.append("The two Kings cannot begin on touching squares.")
            self._validate_ability_prerequisites(payload, effective, result)
            self._validate_victory_reachability(
                payload,
                effective,
                result,
                request.boardRows,
                request.boardCols,
                pieces,
            )
        else:
            self._validate_gambit(request, result, pieces)

        return result

    def _validate_ability_prerequisites(self, payload, placements: list[dict], result) -> None:
        if not payload.specialAbilities.enabled:
            return
        types_by_color = {
            color: {piece["type"] for piece in placements if piece["color"] == color}
            for color in ("white", "black")
        }
        requirements = {
            "getaway": ({"queen"}, "Getaway requires a Queen for both players."),
            "kamikaze": ({"pawn"}, "Kamikaze requires a Pawn for both players."),
            "episcopal": ({"bishop"}, "Episcopal requires a Bishop for both players."),
            "power_of_love": ({"queen"}, "Power of Love requires a Queen for both players."),
        }
        for ability in payload.specialAbilities.allowed:
            requirement = requirements.get(ability)
            if requirement and any(
                not (types_by_color[color] & requirement[0]) for color in ("white", "black")
            ):
                result.warnings.append(requirement[1])

    def _validate_victory_reachability(
        self,
        payload,
        placements: list[dict],
        result,
        board_rows: int,
        board_cols: int,
        pieces: dict[str, PieceDefinition],
    ) -> None:
        mode = payload.victory.mode
        material_issue = self.material.issue(mode, placements, pieces)
        if material_issue:
            result.errors.append(material_issue)
        if mode == "royal_center":
            targets = set(objective_center_squares(board_rows, board_cols))
            if any(
                piece["type"] == "king" and (piece["row"], piece["col"]) in targets
                for piece in placements
            ):
                result.errors.append(
                    "Kings must begin outside the Royal Center objective squares."
                )
        if mode == "point_race":
            totals = {"white": 0, "black": 0}
            for piece in placements:
                color = piece["color"]
                if color not in totals or piece["type"] in {"barricade", "diplomat"}:
                    continue
                if piece["type"] == "king":
                    value = payload.victory.kingPoints
                else:
                    default = pieces.get(piece["type"])
                    value = payload.piecePoints.get(piece["type"], default.points if default else 0)
                totals[color] += int(value or 0)
            reachable = min(totals.values())
            if payload.victory.targetPoints > reachable:
                result.errors.append(
                    f"The point target cannot exceed {reachable}; both players need enough "
                    "opposing material to reach it."
                )

    def _validate_gambit(
        self,
        request: CreateGameRequest,
        result: ConfigurationValidation,
        pieces: dict[str, PieceDefinition],
    ) -> None:
        payload = request.configuration
        assert payload is not None
        gambit = payload.gambit
        if gambit.setupRows > request.boardRows // 2:
            result.errors.append("Private setup rows cannot cross the board midpoint.")
        if gambit.maxPieces > gambit.setupRows * request.boardCols:
            result.errors.append("Deployment rows do not have enough squares for the army cap.")
        if gambit.maxQueens > max(0, gambit.maxPieces - 1):
            result.errors.append("The Queen limit must leave one army slot for the King.")

        enabled = set(payload.enabledPieces) - {"barricade"}
        points = {
            piece_type: int(
                payload.piecePoints.get(piece_type, pieces[piece_type].points) or 0
            )
            for piece_type in enabled
            if piece_type in pieces
        }
        caps = {
            piece_type: int(gambit.pieceCaps.get(piece_type, gambit.maxPieces))
            for piece_type in enabled
        }
        caps["king"] = 1
        caps["queen"] = gambit.maxQueens
        if any(cap > gambit.maxPieces for cap in caps.values()):
            result.errors.append("A piece limit cannot exceed the complete army cap.")
        if points.get("king", 0) > gambit.budget:
            result.errors.append(
                "The Gambit point limit must be high enough to include the required King."
            )
        if not self.material.can_build_sufficient_army(
            victory_mode=payload.victory.mode,
            definitions=pieces,
            enabled_piece_types=enabled,
            piece_caps=caps,
            piece_costs=points,
            budget=gambit.budget,
            max_pieces=gambit.maxPieces,
        ):
            result.errors.append(INSUFFICIENT_MATERIAL_MESSAGE)

        if gambit.draftEnabled:
            pool = build_default_draft_pool(enabled)
            pool.update(gambit.draftPool)
            unknown_pool = sorted(set(gambit.draftPool) - enabled)
            if unknown_pool:
                result.errors.append(f"Draft pool piece is not enabled: {unknown_pool[0]}.")
            if "barricade" in gambit.draftPool:
                result.errors.append("Barricades are neutral and cannot enter the army draft.")
            if pool.get("king", 0) != 2:
                result.errors.append(
                    "Draft Gambit requires exactly two Kings, one preassigned to each army."
                )
            if sum(pool.values()) < 2:
                result.errors.append("The shared draft pool needs pieces for both players.")

        if payload.specialAbilities.enabled:
            requirements = {
                "getaway": ({"queen"}, "Getaway requires an enabled Queen."),
                "kamikaze": ({"pawn"}, "Kamikaze requires enabled Pawns."),
                "episcopal": ({"bishop"}, "Episcopal requires enabled Bishops."),
                "power_of_love": ({"queen"}, "Power of Love requires enabled Queens."),
            }
            for ability in payload.specialAbilities.allowed:
                requirement = requirements.get(ability)
                if requirement and not (enabled & requirement[0]):
                    result.errors.append(requirement[1])
