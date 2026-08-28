import { useEffect, useRef, useState } from "react";

import Button from "./ui/Button";
import Dialog from "./ui/Dialog";

function BotSetupDialog({ open, profiles = [], onClose, onStart, loading = false, error = "" }) {
  const defaultProfile = profiles.find((profile) => profile.targetElo === 800) || profiles[0];
  const engineId = defaultProfile?.engineId || "stockfish";
  const engineName = defaultProfile?.engineName || "Stockfish 18";
  const usesFairy = engineId === "fairy-stockfish";
  const usesChass = engineId === "chass";
  const eyebrow = usesChass
    ? "Custom Variant Bot"
    : usesFairy
      ? "Static Variant Bot"
      : "Classic Chass Bot";
  const ratingNote = usesChass
    ? "Chass ratings are conservative estimates. The bot understands the active rules, custom pieces, abilities, command powers, and setup phases, but remains experimental and weaker than Stockfish."
    : usesFairy
      ? "Fairy ratings are conservative estimates for static variants and are not calibrated across every board or win condition."
      : "Ratings are estimates. Lower levels use controlled move variation; stronger levels use Stockfish's native strength limit.";
  const [profileId, setProfileId] = useState(defaultProfile?.id || "");
  const [humanColor, setHumanColor] = useState("white");
  const defaultProfileRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setProfileId(defaultProfile?.id || "");
    setHumanColor("white");
  }, [defaultProfile?.id, open]);

  return (
    <Dialog
      open={open}
      onClose={loading ? () => {} : onClose}
      closeLabel="Close bot setup"
      eyebrow={eyebrow}
      title="Choose Your Opponent"
      description={`This configuration uses ${engineName}. Select an estimated strength and your side.`}
      className="bot-setup-dialog"
      initialFocusRef={defaultProfileRef}
      closeOnBackdrop={!loading}
      actions={(
        <>
          <Button variant="secondary" disabled={loading} onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={loading}
            loadingLabel="Starting Match..."
            disabled={!profileId}
            onClick={() => onStart({ profileId, humanColor })}
          >
            Start Game
          </Button>
        </>
      )}
    >
      <fieldset className="bot-profile-fieldset">
        <legend>Estimated Elo</legend>
        <div className="bot-profile-grid">
          {profiles.map((profile) => (
            <label
              key={profile.id}
              className={`bot-profile-option ${profileId === profile.id ? "is-selected" : ""}`}
            >
              <input
                ref={profile.id === defaultProfile?.id ? defaultProfileRef : undefined}
                type="radio"
                name="bot-profile"
                value={profile.id}
                checked={profileId === profile.id}
                disabled={loading}
                onChange={() => setProfileId(profile.id)}
              />
              <span>
                <strong>{profile.targetElo}</strong>
                <b>{profile.label}</b>
                <small>{profile.description}</small>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="bot-color-fieldset">
        <legend>Your Side</legend>
        <div className="bot-color-options">
          {[
            ["white", "White"],
            ["black", "Black"],
            ["random", "Random"],
          ].map(([value, label]) => (
            <label key={value} className={humanColor === value ? "is-selected" : ""}>
              <input
                type="radio"
                name="human-color"
                value={value}
                checked={humanColor === value}
                disabled={loading}
                onChange={() => setHumanColor(value)}
              />
              <span>{label}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <p className="bot-rating-note">
        {ratingNote}
      </p>
      {error ? <p className="bot-setup-error" role="alert">{error}</p> : null}
    </Dialog>
  );
}

export default BotSetupDialog;
