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
  onLoadEarlierHistory,
  historyLoading,
}) {
  const [selectedPower, setSelectedPower] = useState(null);
  const [selectedGlobalActionType, setSelectedGlobalActionType] = useState(null);
  const [evolveTo, setEvolveTo] = useState("knight");
  const lastMove = game.history.length ? game.history[game.history.length - 1] : null;
  const powerTargets = selectedPower
    ? game.affinity?.legalPowerTargets?.[selectedPower] || []
    : [];
  const powerTargetSet = useMemo(
    () => new Set(powerTargets.map((target) => `${target.row}-${target.col}`)),
    [powerTargets]
  );
  const globalActions = useMemo(
    () => game.availableActions.filter(
      (action) => !action.source && action.actionType === selectedGlobalActionType
    ),
    [game.availableActions, selectedGlobalActionType]
  );

  useEffect(() => {
    setSelectedPower(null);
    setSelectedGlobalActionType(null);
  }, [game.currentPlayer, game.phase]);

  useEffect(() => {
    if (selectedGlobalActionType && !globalActions.length) {
      setSelectedGlobalActionType(null);
    }
  }, [globalActions.length, selectedGlobalActionType]);

  const selectPower = (power) => {
    setSelectedPower(power);
    if (power) setSelectedGlobalActionType(null);
  };

  const selectGlobalAction = (actionType) => {
    setSelectedGlobalActionType(actionType);
    if (actionType) setSelectedPower(null);
  };

  const handleAction = (action) => {
    setSelectedGlobalActionType(null);
    onAction(action);
  };

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
      <EffectsPanel
        game={game}
        catalog={catalog}
        onAction={handleAction}
        actionLoading={actionLoading}
        selectedGlobalActionType={selectedGlobalActionType}
        onSelectGlobalActionType={selectGlobalAction}
      >
        {game.affinity?.enabled ? (
          <CommandPanel
            game={game}
            interactive={interactive && !actionLoading}
            selectedPower={selectedPower}
            onSelectPower={selectPower}
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
          countdowns={game.countdowns}
          terrain={game.terrain}
          globalActions={globalActions}
          availableActions={selectedPower || selectedGlobalActionType ? [] : game.availableActions}
          onAction={handleAction}
        />
        <p className="board-detail-hint">Blue dots move pieces. Red targets attack or sacrifice; teal, gold, and ember targets use special actions. Double-tap for details.</p>
      </section>

      <GameInfoPanel
        game={game}
        onLoadEarlierHistory={onLoadEarlierHistory}
        historyLoading={historyLoading}
      />
    </main>
  );
}

export default PlayPage;
