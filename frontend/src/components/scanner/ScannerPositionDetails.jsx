import { useState } from "react";
import Disclosure from "../ui/Disclosure";
import FormField from "../ui/FormField";
import ScannerIcon from "./ScannerIcon";

function ScannerPositionDetails({ confirmed, onConfirmationChange }) {
  const [currentPlayer, setCurrentPlayer] = useState("white");
  const [castlingRights, setCastlingRights] = useState({
    whiteKing: false,
    whiteQueen: false,
    blackKing: false,
    blackQueen: false,
  });
  const [enPassant, setEnPassant] = useState("none");

  return (
    <section
      className="scanner-panel scanner-position-panel"
      aria-labelledby="scanner-position-title"
    >
      <header className="scanner-panel-header">
        <div>
          <span className="scanner-overline">
            What the photo cannot tell us
          </span>
          <h2 id="scanner-position-title">Confirm the game details</h2>
        </div>
        <span className="scanner-step-label">03</span>
      </header>
      <div className="scanner-position-grid">
        <fieldset className="scanner-turn-field">
          <legend>Whose turn is it?</legend>
          <p>Choose the player who moves next.</p>
          <div className="scanner-turn-options">
            {["white", "black"].map((color) => (
              <label
                className={`scanner-turn-option${currentPlayer === color ? " is-selected" : ""}`}
                key={color}
              >
                <input
                  type="radio"
                  name="scanner-current-player"
                  value={color}
                  checked={currentPlayer === color}
                  onChange={() => {
                    setCurrentPlayer(color);
                    setEnPassant("none");
                    onConfirmationChange(false);
                  }}
                />
                <span className={`scanner-color-dot ${color}`} />
                <strong>{color === "white" ? "White" : "Black"} to move</strong>
                <ScannerIcon name="check" />
              </label>
            ))}
          </div>
        </fieldset>
        <div className="scanner-rights-field">
          <h3>Can either side still castle?</h3>
          <p>Enable only if the King and that Rook have never moved.</p>
          <div className="scanner-castling-grid">
            {[
              { color: "White", prefix: "white" },
              { color: "Black", prefix: "black" },
            ].map(({ color, prefix }) => (
              <fieldset key={color}>
                <legend>{color}</legend>
                {[
                  { side: "Kingside", key: "King", notation: "O-O" },
                  { side: "Queenside", key: "Queen", notation: "O-O-O" },
                ].map(({ side, key, notation }) => (
                  <label className="scanner-check-option" key={key}>
                    <input
                      type="checkbox"
                      checked={castlingRights[`${prefix}${key}`]}
                      onChange={(event) => {
                        setCastlingRights((current) => ({
                          ...current,
                          [`${prefix}${key}`]: event.target.checked,
                        }));
                        onConfirmationChange(false);
                      }}
                    />
                    <span>{side}</span>
                    <small>{notation}</small>
                  </label>
                ))}
              </fieldset>
            ))}
          </div>
        </div>
      </div>
      <Disclosure
        className="scanner-en-passant"
        summary={
          <span>
            <strong>En passant &amp; move history</strong>
            <small>Optional details for a position already in progress</small>
          </span>
        }
      >
        <div className="scanner-en-passant-grid">
          <FormField
            label="En passant target"
            description="Only available immediately after an opposing Pawn moves two squares. Select the square that a capturing Pawn would move onto."
          >
            <select
              value={enPassant}
              onChange={(event) => {
                setEnPassant(event.target.value);
                onConfirmationChange(false);
              }}
            >
              <option value="none">None / not known</option>
              {Array.from(
                "abcdefgh",
                (file) => `${file}${currentPlayer === "white" ? "6" : "3"}`,
              ).map((square) => (
                <option key={square} value={square}>
                  {square}
                </option>
              ))}
            </select>
          </FormField>
          <div className="scanner-history-note">
            <ScannerIcon name="info" />
            <div>
              <strong>Continue from this position</strong>
              <p>
                A photo cannot recover earlier moves, captures, clocks, or draw
                counters. Recording will start from the confirmed board.
              </p>
            </div>
          </div>
        </div>
      </Disclosure>
      <label className="scanner-confirm-option">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => onConfirmationChange(event.target.checked)}
        />
        <span>
          <strong>This board and the game details look right.</strong>
          <small>Check piece colors, orientation, and whose turn it is.</small>
        </span>
      </label>
    </section>
  );
}

export default ScannerPositionDetails;
