import { useEffect, useMemo, useState } from "react";

import ChessBoard from "../components/ChessBoard";
import MoveHistoryPanel from "../components/MoveHistoryPanel";


const PIECE_ORDER = ["king", "queen", "rook", "bishop", "knight", "pawn"];

const POWER_COPY = {
  reinforce: {
    label: "Reinforce",
    kicker: "Add one Pawn",
    description: "Deploy a Pawn on an empty square in your configured home rows.",
  },
  evolve: {
    label: "Evolve",
    kicker: "Upgrade one Pawn",
    description: "Replace one of your Pawns with a Knight or Bishop.",
  },
  stronghold: {
    label: "Stronghold",
    kicker: "Deploy one Rook",
    description: "Add a Rook to an empty square in your first three ranks.",
  },
};

function title(value) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "";
}

function setupRowsFor(color, rows, count) {
  if (color === "white") {
    return Array.from({ length: count }, (_, index) => rows - count + index);
  }
  return Array.from({ length: count }, (_, index) => index);
}

function GambitHandoff({ game, onHandoff, actionLoading }) {
  const ready = game.gambit.deploymentReady;
  const nextColor = ready.white && !ready.black ? "black" : "white";

  return (
    <main className="gambit-handoff-shell">
      <section className="gambit-handoff-card">
        <div className="handoff-seal" aria-hidden="true">
          {nextColor === "white" ? "W" : "B"}
        </div>
        <span className="eyebrow">Private handoff</span>
        <h1>Pass the screen to {title(nextColor)}</h1>
        <p>
          {title(ready.white && !ready.black ? "white" : "black")}'s army is locked and
          hidden. The next player should take the device before continuing.
        </p>
        {game.gambit.setupMessage ? (
          <p className="gambit-opening-warning">{game.gambit.setupMessage}</p>
        ) : null}
        <button type="button" disabled={actionLoading} onClick={onHandoff}>
          {actionLoading ? "Securing board..." : `I am ${title(nextColor)} - Begin Setup`}
        </button>
      </section>
    </main>
  );
}

function DeploymentStatus({ game }) {
  const ready = game.gambit.deploymentReady;
  return (
    <div className="deployment-status-row" aria-label="Deployment readiness">
      {(["white", "black"]).map((color) => (
        <span
          key={color}
          className={`deployment-seat ${ready[color] ? "ready" : "preparing"}`}
        >
          <i className={`seat-dot ${color}`} />
          {title(color)}: {ready[color] ? "ready" : "preparing"}
        </span>
      ))}
    </div>
  );
}

function GambitDeployment({
  game,
  boardFlipped,
  actionLoading,
  onDeploymentChange,
  onReady,
}) {
  const gambit = game.gambit;
  const color = gambit.viewerColor || gambit.editableColor || "white";
  const editable = Boolean(gambit.editableColor);
  const [selectedPiece, setSelectedPiece] = useState("king");
  const definitionMap = useMemo(
    () => new Map(game.pieceDefinitions.map((definition) => [definition.type, definition])),
    [game.pieceDefinitions]
  );
  const availablePieceTypes = useMemo(() => {
    const enabled = (game.configuration?.enabledPieces || PIECE_ORDER).filter(
      (pieceType) => pieceType !== "barricade"
    );
    return [...enabled].sort((left, right) => {
      const leftIndex = PIECE_ORDER.indexOf(left);
      const rightIndex = PIECE_ORDER.indexOf(right);
      if (leftIndex === -1 && rightIndex === -1) return left.localeCompare(right);
      if (leftIndex === -1) return 1;
      if (rightIndex === -1) return -1;
      return leftIndex - rightIndex;
    });
  }, [game.configuration?.enabledPieces]);
  const rows = game.boardRows ?? game.boardSize;
  const ownRows = setupRowsFor(color, rows, gambit.config.setupRows);
  const opponentRows = setupRowsFor(
    color === "white" ? "black" : "white",
    rows,
    gambit.config.setupRows
  );
  const summary = gambit.setupSummary;
  const counts = summary?.counts || {};

  const handleSquare = (row, col) => {
    if (!editable || actionLoading || !ownRows.includes(row)) {
      return;
    }
    const piece = game.board[row][col];
    if (piece?.color === "neutral") {
      return;
    }
    if (piece) {
      onDeploymentChange({ action: "remove", row, col });
      return;
    }
    onDeploymentChange({ action: "place", row, col, pieceType: selectedPiece });
  };

  return (
    <main className="gambit-deployment-layout">
      <section className="gambit-deployment-board">
        <header className="deployment-heading">
          <div>
            <span className="eyebrow">Hidden deployment</span>
            <h1>{title(color)} War Room</h1>
            <p>
              Select a piece, then place it inside your highlighted home ranks. Click a
              deployed piece to remove it.
            </p>
          </div>
          <DeploymentStatus game={game} />
        </header>

        <ChessBoard
          board={game.board}
          boardRows={rows}
          boardCols={game.boardCols ?? game.boardSize}
          selectedSquare={null}
          validMoves={[]}
          onSquareClick={handleSquare}
          lastMove={null}
          boardFlipped={boardFlipped}
          interactive={editable && !actionLoading}
          affinitySquares={gambit.config.affinitySquares}
          editableRows={ownRows}
          foggedRows={opponentRows}
          showCoordinates
        />

        {gambit.config.affinityEnabled ? (
          <div className="affinity-legend">
            <span><i className="affinity-swatch white" /> White affinity squares</span>
            <span><i className="affinity-swatch black" /> Black affinity squares</span>
          </div>
        ) : null}
      </section>

      <aside className="war-chest-panel">
        <div className="war-chest-heading">
          <div>
            <span className="eyebrow">Army builder</span>
            <h2>War Chest</h2>
          </div>
          <div className="budget-dial" aria-label={`${summary?.pointsRemaining ?? 39} points left`}>
            <strong>{summary?.pointsRemaining ?? gambit.config.budget}</strong>
            <span>left</span>
          </div>
        </div>

        {!game.ready && game.mode === "online" ? (
          <div className="gambit-waiting-note">
            The War Chest unlocks after both player seats are claimed. Share the invite above.
          </div>
        ) : null}

        {gambit.deploymentReady[color] ? (
          <div className="gambit-locked-note">
            <strong>Your army is locked.</strong>
            <span>Waiting for {title(color === "white" ? "black" : "white")} to finish.</span>
          </div>
        ) : null}

        <div className="war-chest-grid">
          {availablePieceTypes.map((pieceType) => {
            const definition = definitionMap.get(pieceType);
            const cost = gambit.config.piecePoints[pieceType];
            const cap = gambit.config.pieceCaps[pieceType];
            const count = counts[pieceType] || 0;
            const atCap = count >= cap;
            return (
              <button
                type="button"
                key={pieceType}
                className={`war-piece ${selectedPiece === pieceType ? "selected" : ""}`}
                disabled={!editable || actionLoading || atCap}
                onClick={() => setSelectedPiece(pieceType)}
              >
                <span className="war-piece-symbol">{definition?.symbols?.[color]}</span>
                <span className="war-piece-copy">
                  <strong>{definition?.displayName || title(pieceType)}</strong>
                  <small>{cost === 0 ? "Free" : `${cost} point${cost === 1 ? "" : "s"}`}</small>
                </span>
                <span className="war-piece-cap">{count}/{cap}</span>
              </button>
            );
          })}
        </div>

        <div className="army-totals">
          <div>
            <span>Material</span>
            <strong>{summary?.pointsSpent ?? 0} / {gambit.config.budget}</strong>
          </div>
          <div>
            <span>Army size</span>
            <strong>{summary?.pieceCount ?? 0} / {gambit.config.maxPieces}</strong>
          </div>
        </div>

        <section className="deployment-checklist">
          <h3>Lock-in check</h3>
          {summary?.issues?.length ? (
            <ul>
              {summary.issues.map((issue) => <li key={issue}>{issue}</li>)}
            </ul>
          ) : (
            <p className="deployment-valid">Army legal. Ready to lock in.</p>
          )}
        </section>

        {gambit.setupMessage ? (
          <p className="gambit-opening-warning">{gambit.setupMessage}</p>
        ) : null}

        <div className="deployment-actions">
          <button
            type="button"
            className="secondary"
            disabled={!editable || actionLoading}
            onClick={() => onDeploymentChange({ action: "undo" })}
          >
            Undo
          </button>
          <button
            type="button"
            className="secondary"
            disabled={!editable || actionLoading || !summary?.pieceCount}
            onClick={() => onDeploymentChange({ action: "clear" })}
          >
            Clear
          </button>
          <button
            type="button"
            className="lock-army-button"
            disabled={!editable || actionLoading || !summary?.canReady}
            onClick={onReady}
          >
            {actionLoading ? "Locking..." : "Lock In Army"}
          </button>
        </div>
      </aside>
    </main>
  );
}

function CommandPanel({ game, interactive, selectedPower, onSelectPower, evolveTo, setEvolveTo }) {
  const gambit = game.gambit;
  const color = gambit.viewerColor || game.currentPlayer;
  const points = gambit.commandPoints[color] || 0;
  const controlled = gambit.affinityControlled[color];
  const primed = gambit.affinityPrimed[color];

  return (
    <section className="command-panel">
      <header className="command-heading">
        <div>
          <span className="eyebrow">{title(color)} command</span>
          <h2>Command Points</h2>
        </div>
        <div className="command-pips" aria-label={`${points} of ${gambit.config.commandPointCap} command points`}>
          {Array.from({ length: gambit.config.commandPointCap }).map((_, index) => (
            <i key={index} className={index < points ? "filled" : ""} />
          ))}
        </div>
      </header>

      <div className={`affinity-readout ${controlled ? "controlled" : ""}`}>
        <strong>{controlled ? "Affinity held" : "Affinity contested"}</strong>
        <span>
          {!gambit.config.affinityEnabled
            ? "Affinity squares are disabled for this game."
            : primed
            ? "Keep both squares through the enemy turn to earn 1 point."
            : "Occupy both marked squares at the end of your turn to prime a point."}
        </span>
      </div>

      <div className="power-list">
        {Object.entries(POWER_COPY).map(([power, copy]) => {
          const cost = gambit.config.powerCosts[power];
          const usage = gambit.powerUsage[color]?.[power] || 0;
          const cap = gambit.config.powerUsageCaps[power];
          const targets = gambit.legalPowerTargets[power] || [];
          const available = interactive && points >= cost && usage < cap && targets.length > 0;
          return (
            <button
              type="button"
              key={power}
              className={`power-card ${selectedPower === power ? "selected" : ""}`}
              disabled={!available}
              onClick={() => onSelectPower(selectedPower === power ? null : power)}
            >
              <span className="power-cost">{cost} CP</span>
              <span className="power-copy">
                <strong>{copy.label}</strong>
                <small>{copy.kicker}</small>
                <span>{copy.description}</span>
              </span>
              <span className="power-uses">{usage}/{cap}</span>
            </button>
          );
        })}
      </div>

      {selectedPower === "evolve" ? (
        <div className="evolve-choice" role="group" aria-label="Choose evolved piece">
          <span>Evolve into</span>
          {(["knight", "bishop"]).map((pieceType) => (
            <button
              type="button"
              key={pieceType}
              className={evolveTo === pieceType ? "active" : ""}
              onClick={() => setEvolveTo(pieceType)}
            >
              {title(pieceType)}
            </button>
          ))}
        </div>
      ) : null}

      {selectedPower ? (
        <p className="power-instruction">
          Select one of the pulsing board squares. This action uses your full turn.
        </p>
      ) : (
        <p className="power-instruction muted">
          Command powers may block check, create check, or deliver checkmate.
        </p>
      )}
    </section>
  );
}

function GambitPlay({
  game,
  selectedSquare,
  onSquareClick,
  boardFlipped,
  interactive,
  actionLoading,
  onPower,
  onAction,
}) {
  const [selectedPower, setSelectedPower] = useState(null);
  const [evolveTo, setEvolveTo] = useState("knight");
  const lastMove = game.history.length ? game.history[game.history.length - 1] : null;
  const powerTargets = selectedPower
    ? game.gambit.legalPowerTargets[selectedPower] || []
    : [];
  const powerTargetSet = useMemo(
    () => new Set(powerTargets.map((target) => `${target.row}-${target.col}`)),
    [powerTargets]
  );

  useEffect(() => {
    setSelectedPower(null);
  }, [game.currentPlayer, game.phase]);

  const handleSquare = (row, col) => {
    if (selectedPower) {
      if (powerTargetSet.has(`${row}-${col}`)) {
        onPower({
          power: selectedPower,
          row,
          col,
          ...(selectedPower === "evolve" ? { evolveTo } : {}),
        });
        setSelectedPower(null);
      }
      return;
    }
    onSquareClick(row, col);
  };

  return (
    <main className="gambit-play-layout">
      <section className="board-section gambit-battle-board">
        <ChessBoard
          board={game.board}
          boardRows={game.boardRows ?? game.boardSize}
          boardCols={game.boardCols ?? game.boardSize}
          selectedSquare={selectedSquare}
          validMoves={game.validMoves}
          onSquareClick={handleSquare}
          lastMove={lastMove}
          boardFlipped={boardFlipped}
          interactive={interactive && !actionLoading}
          extraTargets={powerTargets}
          affinitySquares={game.gambit.config.affinitySquares}
          showCoordinates
        />
      </section>

      <aside className="gambit-play-sidebar">
        <CommandPanel
          game={game}
          interactive={interactive && !actionLoading}
          selectedPower={selectedPower}
          onSelectPower={setSelectedPower}
          evolveTo={evolveTo}
          setEvolveTo={setEvolveTo}
        />
        <MoveHistoryPanel
          rules={game.rules}
          history={game.history}
          capturedPieces={game.capturedPieces}
          lastMoveExplanation={game.lastMoveExplanation}
          gameStatus={game.gameStatus}
          winner={game.winner}
          score={game.score}
          abilities={game.abilities}
          countdowns={game.countdowns}
          availableActions={game.availableActions}
          clock={game.clock}
          onAction={onAction}
          actionLoading={actionLoading}
          boardRows={game.boardRows ?? game.boardSize}
          compactRules
        />
      </aside>
    </main>
  );
}

function GambitPage(props) {
  if (props.game.phase === "handoff") {
    return (
      <GambitHandoff
        game={props.game}
        onHandoff={props.onHandoff}
        actionLoading={props.actionLoading}
      />
    );
  }

  if (["lobby", "deployment"].includes(props.game.phase)) {
    return (
      <GambitDeployment
        game={props.game}
        boardFlipped={props.boardFlipped}
        actionLoading={props.actionLoading}
        onDeploymentChange={props.onDeploymentChange}
        onReady={props.onReady}
      />
    );
  }

  return <GambitPlay {...props} />;
}

export default GambitPage;
