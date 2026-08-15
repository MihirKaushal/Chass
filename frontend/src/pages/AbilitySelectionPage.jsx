import { useEffect, useState } from "react";

import { effectiveCatalogEntry } from "../variantTuning";

function title(value) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) : "";
}

function AbilitySelectionPage({ game, catalog, onSelect, actionLoading }) {
  const color = game.abilities.editableColor || "white";
  const allowed = new Set(game.abilities.allowed);
  const abilityParameters = game.configuration?.specialAbilities?.parameters || {};
  const abilities = (catalog?.specialAbilities || [])
    .filter((ability) => allowed.has(ability.id))
    .map((ability) => effectiveCatalogEntry(ability, abilityParameters[ability.id]));
  const maxChoices = game.abilities.maxPerPlayer || 1;
  const [choices, setChoices] = useState([]);

  useEffect(() => {
    setChoices([]);
  }, [color, game.id]);

  const toggleChoice = (abilityId) => {
    setChoices((current) => {
      if (current.includes(abilityId)) {
        return current.filter((item) => item !== abilityId);
      }
      if (current.length >= maxChoices) {
        return current;
      }
      return [...current, abilityId];
    });
  };
  const choiceLabel = maxChoices === 1 ? "One Ability" : `${maxChoices} Abilities`;

  return (
    <main className="ability-selection-shell">
      <section className="ability-selection-card">
        <header>
          <span className="eyebrow">Private Loadout</span>
          <h1>{title(color)}, Choose {choiceLabel}</h1>
          <p>
            Build your private loadout, then lock every choice together. The opponent sees only
            that you are ready until both players have selected.
          </p>
        </header>
        {!game.ready && game.mode === "online" ? (
          <p className="ability-waiting">Waiting for the second player to join the room.</p>
        ) : null}
        <div className="ability-selection-grid">
          {abilities.map((ability) => (
            <button
              type="button"
              key={ability.id}
              className={choices.includes(ability.id) ? "selected" : ""}
              disabled={actionLoading || !game.ready || !game.abilities.editableColor}
              onClick={() => toggleChoice(ability.id)}
            >
              <i>{ability.icon}</i>
              <span><strong>{ability.name}</strong><small>{ability.summary}</small></span>
              <b>{choices.includes(ability.id) ? "Selected" : "Choose"}</b>
            </button>
          ))}
        </div>
        {game.abilities.viewerSelection?.length ? (
          <p className="ability-locked">Your loadout is locked. Waiting for the other player.</p>
        ) : (
          <button
            type="button"
            className="ability-lock-button"
            disabled={actionLoading || !game.ready || !game.abilities.editableColor || choices.length !== maxChoices}
            onClick={() => onSelect(choices)}
          >
            {actionLoading ? "Locking Loadout..." : `Lock ${choices.length} / ${maxChoices}`}
          </button>
        )}
      </section>
    </main>
  );
}

function AbilityHandoffPage({ game, onContinue, actionLoading }) {
  const nextColor = game.abilities.selected.white?.length && !game.abilities.selected.black?.length ? "black" : "white";
  return (
    <main className="gambit-handoff-shell">
      <section className="gambit-handoff-card">
        <div className="handoff-seal" aria-hidden="true">{nextColor === "white" ? "W" : "B"}</div>
        <span className="eyebrow">Private Ability Handoff</span>
        <h1>Pass The Screen To {title(nextColor)}</h1>
        <p>The previous choice is locked and hidden. Continue only after the next player has the device.</p>
        <button type="button" disabled={actionLoading} onClick={onContinue}>
          {actionLoading ? "Securing Choice..." : `I Am ${title(nextColor)} - Continue`}
        </button>
      </section>
    </main>
  );
}

export { AbilityHandoffPage };
export default AbilitySelectionPage;
