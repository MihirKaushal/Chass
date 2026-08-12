function title(value) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) : "";
}

function AbilitySelectionPage({ game, catalog, onSelect, actionLoading }) {
  const color = game.abilities.editableColor || "white";
  const allowed = new Set(game.abilities.allowed);
  const abilities = (catalog?.specialAbilities || []).filter((ability) => allowed.has(ability.id));

  return (
    <main className="ability-selection-shell">
      <section className="ability-selection-card">
        <header>
          <span className="eyebrow">Private Loadout</span>
          <h1>{title(color)}, Choose One Ability</h1>
          <p>
            Your choice locks immediately. The opponent sees only that you are ready until both
            players have selected.
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
              disabled={actionLoading || !game.ready || !game.abilities.editableColor}
              onClick={() => onSelect(ability.id)}
            >
              <i>{ability.icon}</i>
              <span><strong>{ability.name}</strong><small>{ability.summary}</small></span>
              <b>Choose</b>
            </button>
          ))}
        </div>
        {game.abilities.viewerSelection ? (
          <p className="ability-locked">Your choice is locked. Waiting for the other player.</p>
        ) : null}
      </section>
    </main>
  );
}

function AbilityHandoffPage({ game, onContinue, actionLoading }) {
  const nextColor = game.abilities.selected.white && !game.abilities.selected.black ? "black" : "white";
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
