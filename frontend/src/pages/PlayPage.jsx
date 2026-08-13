import ChessBoard from "../components/ChessBoard";
import { EffectsPanel, GameInfoPanel } from "../components/MoveHistoryPanel";

function PlayPage({
  game,
  selectedSquare,
  onSquareClick,
  boardFlipped,
  interactive,
  onAction,
  actionLoading,
  catalog,
}) {
  const lastMove = game.history.length ? game.history[game.history.length - 1] : null;

  return (
    <main className="play-layout play-layout-three-column">
      <EffectsPanel game={game} catalog={catalog} onAction={onAction} actionLoading={actionLoading} />

      <section className="board-section">
        <ChessBoard
          board={game.board}
          boardRows={game.boardRows ?? game.boardSize}
          boardCols={game.boardCols ?? game.boardSize}
          selectedSquare={selectedSquare}
          validMoves={game.validMoves}
          onSquareClick={onSquareClick}
          lastMove={lastMove}
          boardFlipped={boardFlipped}
          interactive={interactive}
          pieceDetailsMode="double-tap"
        />
        <p className="board-detail-hint">Double-tap or double-click a piece to view details.</p>
      </section>

      <GameInfoPanel game={game} />
    </main>
  );
}

export default PlayPage;
