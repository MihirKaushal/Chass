import { useEffect, useMemo, useState } from "react";

import ActiveActionStrip from "../components/ActiveActionStrip";
import BoardMarkerGuide from "../components/BoardMarkerGuide";
import ChessBoard from "../components/ChessBoard";
import GameBriefing from "../components/GameBriefing";
import MatchPredictor from "../components/MatchPredictor";
import { EffectsPanel, GameInfoPanel } from "../components/MoveHistoryPanel";
import ResponsivePlayLayout from "../components/ResponsivePlayLayout";
import { actionsForGlobalSelection } from "../specialActionSelection";
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
  matchAnalysis,
  analysisRefreshing,
  onRetryAnalysis,
}) {
  const [selectedPower, setSelectedPower] = useState(null);
  const [selectedGlobalActionKey, setSelectedGlobalActionKey] = useState(null);
  const [selectedBoardAction, setSelectedBoardAction] = useState(null);
  const [evolveTo, setEvolveTo] = useState("knight");
  const lastMove = game.history.length ? game.history[game.history.length - 1] : null;
  const moveCount = game.historyPagination?.totalMoves ?? game.history.length;
  const powerTargets = selectedPower
    ? game.affinity?.legalPowerTargets?.[selectedPower] || []
    : [];
  const powerTargetSet = useMemo(
    () => new Set(powerTargets.map((target) => `${target.row}-${target.col}`)),
    [powerTargets]
  );
  const globalActions = useMemo(
    () => actionsForGlobalSelection(game.availableActions, selectedGlobalActionKey),
    [game.availableActions, selectedGlobalActionKey]
  );

  useEffect(() => {
    setSelectedPower(null);
    setSelectedGlobalActionKey(null);
    setSelectedBoardAction(null);
  }, [game.currentPlayer, game.phase]);

  useEffect(() => {
    if (selectedGlobalActionKey && !globalActions.length) {
      setSelectedGlobalActionKey(null);
    }
  }, [globalActions.length, selectedGlobalActionKey]);

  const selectPower = (power) => {
    setSelectedPower(power);
    if (power) {
      setSelectedGlobalActionKey(null);
      setSelectedBoardAction(null);
    }
  };

  const selectGlobalAction = (selectionKey) => {
    if (selectionKey && selectedSquare) {
      onSquareClick(selectedSquare.row, selectedSquare.col);
    }
    setSelectedGlobalActionKey(selectionKey);
    if (selectionKey) {
      setSelectedPower(null);
      setSelectedBoardAction(null);
    }
  };

  const handleAction = (action) => {
    setSelectedGlobalActionKey(null);
    setSelectedBoardAction(null);
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

  const effectsPanel = (
    <EffectsPanel
      game={game}
      catalog={catalog}
      onAction={handleAction}
      actionLoading={actionLoading}
      selectedGlobalActionKey={selectedGlobalActionKey}
      onSelectGlobalActionKey={selectGlobalAction}
    >
      {game.configuration?.matchPredictorEnabled ? (
        <MatchPredictor
          analysis={matchAnalysis}
          moveCount={moveCount}
          refreshing={analysisRefreshing}
          onRetry={onRetryAnalysis}
        />
      ) : null}
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
  );
  const matchBriefing = (
    <GameBriefing
      boardRows={game.boardRows ?? game.boardSize}
      boardCols={game.boardCols ?? game.boardSize}
      configuration={game.configuration}
      catalog={catalog}
      label="Match Brief"
      className="play-game-briefing"
    />
  );
  const board = (
    <section className="board-section">
        <ActiveActionStrip
          game={game}
          selectedSquare={selectedSquare}
          selectedBoardAction={selectedBoardAction}
          selectedPower={selectedPower}
          selectedGlobalActionKey={selectedGlobalActionKey}
          powerTargets={powerTargets}
        />
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
          availableActions={selectedPower || selectedGlobalActionKey ? [] : game.availableActions}
          onAction={handleAction}
          onActionSelectionChange={setSelectedBoardAction}
        />
        <BoardMarkerGuide />
    </section>
  );
  const infoPanel = (
    <GameInfoPanel
        game={game}
        briefing={matchBriefing}
        onLoadEarlierHistory={onLoadEarlierHistory}
        historyLoading={historyLoading}
    />
  );

  return (
    <ResponsivePlayLayout
      effects={effectsPanel}
      board={board}
      info={infoPanel}
      effectCount={
        (game.countdowns?.length || 0)
        + (game.availableActions?.length ? 1 : 0)
        + (game.configuration?.matchPredictorEnabled ? 1 : 0)
      }
      moveCount={moveCount}
    />
  );
}

export default PlayPage;
