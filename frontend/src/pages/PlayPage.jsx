import { useEffect, useMemo, useState } from "react";

import ChessBoard from "../components/ChessBoard";
import { EffectsPanel, GameInfoPanel } from "../components/MoveHistoryPanel";
import { CommandPanel } from "./GambitPage";

function PlayPage({
  game,
  selectedSquare,
  onSquareClick,
  boardFlipped,
  interactive,
  onAction,
  onPower,
  actionLoading,
  catalog,
}) {
  const [selectedPower, setSelectedPower] = useState(null);
  const [evolveTo, setEvolveTo] = useState("knight");
  const lastMove = game.history.length ? game.history[game.history.length - 1] : null;
  const powerTargets = selectedPower
    ? game.affinity?.legalPowerTargets?.[selectedPower] || []
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
    <main className="play-layout play-layout-three-column">
      <EffectsPanel game={game} catalog={catalog} onAction={onAction} actionLoading={actionLoading}>
        {game.affinity?.enabled ? (
          <CommandPanel
            game={game}
            interactive={interactive && !actionLoading}
            selectedPower={selectedPower}
            onSelectPower={setSelectedPower}
            evolveTo={evolveTo}
            setEvolveTo={setEvolveTo}
          />
        ) : null}
      </EffectsPanel>

      <section className="board-section">
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
          affinitySquares={game.affinity?.enabled ? game.affinity.squares : (game.centerDominion?.squares || {})}
          objectiveSquares={game.royalCenter?.squares || []}
          showCoordinates
          pieceDetailsMode="double-tap"
          availableActions={selectedPower ? [] : game.availableActions}
          onAction={onAction}
          countdowns={game.countdowns}
        />
        <p className="board-detail-hint">Blue dots move pieces. Red targets attack or sacrifice; teal and gold targets use special actions. Double-tap for details.</p>
      </section>

      <GameInfoPanel game={game} />
    </main>
  );
}

export default PlayPage;
