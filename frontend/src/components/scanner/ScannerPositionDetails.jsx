import Disclosure from "../ui/Disclosure";
import FormField from "../ui/FormField";
import ScannerIcon from "./ScannerIcon";

function ScannerPositionDetails({
  confirmed,
  onConfirmationChange,
  details,
  onChange,
  remainingReviews = 0,
}) {
  const { currentPlayer, castlingRights, enPassant } = details;

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
          <p>Defaults to White. Change this if Black moves next.</p>
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
                    onChange({
                      ...details,
                      currentPlayer: color,
                      enPassant: null,
                    });
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
          <p>
            Optional; off by default. Enable only if the King and that Rook have
            never moved and are on their home squares.
          </p>
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
                        onChange({
                          ...details,
                          castlingRights: {
                            ...castlingRights,
                            [`${prefix}${key}`]: event.target.checked,
                          },
                        });
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
              value={enPassant || "none"}
              onChange={(event) => {
                onChange({
                  ...details,
                  enPassant:
                    event.target.value === "none" ? null : event.target.value,
                  halfmoveClock: 0,
                });
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
          <FormField
            label="Halfmove clock"
            description="Moves by either player since the last Pawn move or capture. Leave blank for 0; 100 ends the game under Chass's fifty-move rule."
          >
            <input
              type="number"
              min="0"
              max="99"
              step="1"
              value={details.halfmoveClock}
              onChange={(event) =>
                onChange({ ...details, halfmoveClock: event.target.value })
              }
            />
          </FormField>
          <FormField
            label="Move number"
            description="Optional full-move number for engine analysis. Leave blank for 1; earlier move records are not reconstructed."
          >
            <input
              type="number"
              min="1"
              max="10000"
              step="1"
              value={details.fullmoveNumber}
              onChange={(event) =>
                onChange({ ...details, fullmoveNumber: event.target.value })
              }
            />
          </FormField>
          <div className="scanner-history-note">
            <ScannerIcon name="info" />
            <div>
              <strong>Continue from this position</strong>
              <p>
                A photo cannot recover earlier moves, captures, clocks, or draw
                counters. Move history, captured scores, and repetition tracking
                start from this board. No earlier moves are invented.
              </p>
            </div>
          </div>
        </div>
      </Disclosure>
      <label className="scanner-confirm-option">
        <input
          type="checkbox"
          checked={confirmed}
          disabled={remainingReviews > 0}
          onChange={(event) => onConfirmationChange(event.target.checked)}
        />
        <span>
          <strong>This board and the game details look right.</strong>
          <small>
            {remainingReviews > 0
              ? `Resolve ${remainingReviews} flagged square${remainingReviews === 1 ? "" : "s"} first, then check all 64 squares.`
              : "I checked all 64 squares, piece colors, orientation, and whose turn it is."}
          </small>
        </span>
      </label>
    </section>
  );
}

export default ScannerPositionDetails;
