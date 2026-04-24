import ChessBoard from "../components/ChessBoard";
import MoveHistoryPanel from "../components/MoveHistoryPanel";

function PlayPage({ game, selectedSquare, onSquareClick, boardFlipped }) {
  const lastMove = game.history.length ? game.history[game.history.length - 1] : null;

  return (
    <main className="play-layout">
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
        />
      </section>

      <MoveHistoryPanel
        rules={game.rules}
        history={game.history}
        capturedPieces={game.capturedPieces}
        lastMoveExplanation={game.lastMoveExplanation}
        gameStatus={game.gameStatus}
        winner={game.winner}
        score={game.score}
      />
    </main>
  );
}

export default PlayPage;
