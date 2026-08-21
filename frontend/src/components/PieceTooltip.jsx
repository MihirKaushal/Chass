import PieceGlyph from "./PieceGlyph";
import IconCloseButton from "./IconCloseButton";
import { parameterValueLabel } from "../variantTuning";

function title(value) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "";
}

function quantity(value, singular) {
  return `${value} ${singular}${value === 1 ? "" : "s"}`;
}

function PieceTooltip({ piece, placement = "above", edge = "center", onClose = null }) {
  if (!piece) return null;

  const customRules = piece.customAttributes?.customRules || piece.customAttributes?.rules || [];
  const configuredParameters = piece.customAttributes?.configuredParameters || [];
  const runtimeItems = [];
  if (piece.runtime?.catapult_ready_turn_remaining > 0) {
    runtimeItems.push(`Projectile ready in ${quantity(piece.runtime.catapult_ready_turn_remaining, "own turn")}`);
  }
  if (piece.runtime?.pacified_until_turn_remaining > 0) {
    runtimeItems.push(`Pacified for ${quantity(piece.runtime.pacified_until_turn_remaining, "own turn")}`);
  }
  if (piece.runtime?.love_until_turn_remaining > 0) {
    runtimeItems.push(`Queen mobility for ${quantity(piece.runtime.love_until_turn_remaining, "own turn")}`);
  }
  if (piece.runtime?.recruit_target_name) {
    runtimeItems.push(
      `Recruiting ${piece.runtime.recruit_target_name}: ${piece.runtime.recruit_progress || 0}/${piece.runtime.recruit_threshold || "?"}`
    );
  }
  if (piece.runtime?.pacifications) {
    const retirementThreshold = piece.runtime.diplomat_retirement_threshold
      || configuredParameters.find((parameter) => parameter.id === "retireAfterPacifications")?.value
      || "?";
    runtimeItems.push(`Diplomat pacifications: ${piece.runtime.pacifications}/${retirementThreshold}`);
  }
  if (piece.runtime?.episcopal_ready_turn_remaining > 0) {
    runtimeItems.push(`Episcopal ready in ${piece.runtime.episcopal_ready_turn_remaining} own turns`);
  }
  if (piece.runtime?.cannibal_moves_remaining > 0) {
    runtimeItems.push(
      `${piece.runtime.cannibal_super_state ? "Super State" : `${piece.runtime.cannibal_form_name || "Borrowed"} mobility`}: ${quantity(piece.runtime.cannibal_moves_remaining, "Cannibal move")} remaining; cannot consume`
    );
  }
  (piece.runtime?.diplomat_contacts_status || []).forEach((contact) => {
    runtimeItems.push(`Contact with ${contact.targetName}: ${contact.progress}/${contact.required}`);
  });

  return (
    <div
      className={`piece-tooltip piece-tooltip--${placement} piece-tooltip--${edge} ${onClose ? "piece-tooltip--closable" : ""}`}
      role={onClose ? "dialog" : "tooltip"}
      aria-label={onClose ? `${piece.name} details` : undefined}
    >
      {onClose ? (
        <IconCloseButton
          className="piece-tooltip-close"
          label="Close piece details"
          onClick={(event) => {
            event.stopPropagation();
            onClose();
          }}
        />
      ) : null}
      <div className="tooltip-title">
        <PieceGlyph piece={piece} />
        <strong>{piece.name}</strong>
      </div>
      <span>{title(piece.color)}</span>
      <span>
        {piece.points == null
          ? "No point value"
          : quantity(piece.points, "point")}
      </span>
      {piece.description ? <p><b>Role</b>{piece.description}</p> : null}
      {piece.movement ? <p><b>Movement</b>{piece.movement}</p> : null}
      {configuredParameters.length ? (
        <p>
          <b>Configured Values</b>
          {configuredParameters
            .map((parameter) => `${parameter.label}: ${parameterValueLabel(parameter)}`)
            .join(" · ")}
        </p>
      ) : null}
      {customRules.length ? <p><b>Special Rules</b>{customRules.join(" · ")}</p> : null}
      {runtimeItems.length ? (
        <div className="tooltip-runtime">
          <b>Live Status</b>
          {runtimeItems.map((item) => <span key={item}>{item}</span>)}
        </div>
      ) : null}
    </div>
  );
}

export default PieceTooltip;
