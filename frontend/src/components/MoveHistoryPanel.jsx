function CapturedPieces({ capturedPieces }) {
  const whiteCaptures = capturedPieces?.white || [];
  const blackCaptures = capturedPieces?.black || [];

  return (
    <section className="panel-section">
      <h3>Captured Pieces</h3>
      <div className="captures-row">
        <div>
          <strong>White</strong>
          <p>{whiteCaptures.map((piece) => piece.symbol).join(" ") || "-"}</p>
        </div>
        <div>
          <strong>Black</strong>
          <p>{blackCaptures.map((piece) => piece.symbol).join(" ") || "-"}</p>
        </div>
      </div>
    </section>
  );
}

function ActiveRules({ rules }) {
  return (
    <section className="panel-section">
      <h3>Active Rules</h3>
      <ul className="rule-list">
        {rules
          .filter((rule) => rule.enabled)
          .map((rule) => (
            <li key={rule.id}>
              <span>{rule.name}</span>
              <small>{rule.tier}</small>
            </li>
          ))}
      </ul>
    </section>
  );
}

function GameStateSummary({ gameStatus, winner, score }) {
  const whiteScore = score?.white ?? 0;
  const blackScore = score?.black ?? 0;

  return (
    <section className="panel-section">
      <h3>Game State</h3>
      <div className="state-summary">
        <span>Status: {gameStatus}</span>
        <span>Winner: {winner || "-"}</span>
        <span>
          Score W/B: {whiteScore} / {blackScore}
        </span>
      </div>
    </section>
  );
}

function MoveHistoryPanel({
  rules,
  history,
  capturedPieces,
  lastMoveExplanation,
  gameStatus,
  winner,
  score,
}) {
  return (
    <aside className="history-panel">
      <GameStateSummary gameStatus={gameStatus} winner={winner} score={score} />
      <ActiveRules rules={rules} />
      <CapturedPieces capturedPieces={capturedPieces} />

      <section className="panel-section history-section">
        <h3>Move History</h3>
        {lastMoveExplanation ? <p className="move-explanation">{lastMoveExplanation}</p> : null}
        <ol>
          {[...history].reverse().map((move) => (
            <li key={move.moveNumber}>
              <span>
                {move.moveNumber}. {move.piece} ({move.player})
              </span>
              <small>{move.explanation}</small>
            </li>
          ))}
        </ol>
      </section>
    </aside>
  );
}

export default MoveHistoryPanel;
