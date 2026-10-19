import { useState } from "react";
import { availableBotProfiles } from "../../botGame";
import Button from "../ui/Button";
import FormField from "../ui/FormField";
import ScannerIcon from "./ScannerIcon";

const PLAY_MODES = [
  {
    id: "local",
    icon: "monitor",
    title: "Local Room",
    description: "Continue with someone beside you.",
  },
  {
    id: "online",
    icon: "globe",
    title: "Online Room",
    description: "Invite a friend with a link or code.",
  },
  {
    id: "bot",
    icon: "bot",
    title: "Against A Bot",
    description: "Practice this position against Stockfish.",
  },
];
const SCANNER_BOT_PROFILES = availableBotProfiles(null, "stockfish");

function ScannerContinuePanel({ confirmed }) {
  const [mode, setMode] = useState("local");
  const [humanColor, setHumanColor] = useState("white");
  const [botLevel, setBotLevel] = useState("stockfish-800");
  return (
    <section
      className="scanner-panel scanner-continue-panel"
      aria-labelledby="scanner-continue-title"
    >
      <header className="scanner-panel-header">
        <div>
          <span className="scanner-overline">Pick up the game</span>
          <h2 id="scanner-continue-title">How would you like to play?</h2>
        </div>
        <span className="scanner-coming-label">Coming next</span>
      </header>
      <fieldset className="scanner-play-modes">
        <legend className="scanner-sr-only">Continue game mode</legend>
        {PLAY_MODES.map((option) => (
          <label
            className={`scanner-play-mode${mode === option.id ? " is-selected" : ""}`}
            key={option.id}
          >
            <input
              type="radio"
              name="scanner-play-mode"
              value={option.id}
              checked={mode === option.id}
              onChange={() => setMode(option.id)}
            />
            <span className="scanner-mode-icon">
              <ScannerIcon name={option.icon} />
            </span>
            <span>
              <strong>{option.title}</strong>
              <small>{option.description}</small>
            </span>
            <span className="scanner-mode-selected">
              <ScannerIcon name="check" />
            </span>
          </label>
        ))}
      </fieldset>
      {mode === "bot" ? (
        <div className="scanner-bot-options">
          <FormField label="Play as">
            <select
              value={humanColor}
              onChange={(event) => setHumanColor(event.target.value)}
            >
              <option value="white">White</option>
              <option value="black">Black</option>
            </select>
          </FormField>
          <FormField label="Estimated bot level">
            <select
              value={botLevel}
              onChange={(event) => setBotLevel(event.target.value)}
            >
              {SCANNER_BOT_PROFILES.map((profile) => (
                <option value={profile.id} key={profile.id}>
                  {profile.targetElo} · {profile.label}
                </option>
              ))}
            </select>
          </FormField>
        </div>
      ) : null}
      <div className="scanner-launch-row">
        <div>
          <strong>
            {confirmed
              ? "Example position confirmed"
              : "Review and confirm your position"}
          </strong>
          <p>Game import will be connected after the scanner preview.</p>
        </div>
        <Button
          disabled
          title="Game creation is not connected in this UI preview."
        >
          {mode === "bot"
            ? "Play Against A Bot"
            : mode === "online"
              ? "Create Online Room"
              : "Continue On This Device"}
          <ScannerIcon name="arrow" />
        </Button>
      </div>
    </section>
  );
}

export default ScannerContinuePanel;
