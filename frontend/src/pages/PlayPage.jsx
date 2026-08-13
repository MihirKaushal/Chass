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
}) {
  const lastMove = game.history.length ? game.history[game.history.length - 1] : null;

  return (
    <main className="play-layout play-layout-three-column">
      <EffectsPanel game={game} onAction={onAction} actionLoading={actionLoading} />

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
        />
      </section>

      <GameInfoPanel game={game} />
    </main>
  );
}

export default PlayPage;
