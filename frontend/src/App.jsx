import { useEffect, useMemo, useState } from "react";

import TopNav from "./components/TopNav";
import CustomizePage from "./pages/CustomizePage";
import PlayPage from "./pages/PlayPage";
import {
  createGame,
  getWebSocketUrl,
  makeMove,
  resetGame,
  updatePieces,
  updateRules,
} from "./api/gameApi";

function App() {
  const [activeTab, setActiveTab] = useState("play");
  const [game, setGame] = useState(null);
  const [selectedSquare, setSelectedSquare] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [boardFlipped, setBoardFlipped] = useState(false);

  const selectedMoves = useMemo(() => {
    if (!game || !selectedSquare) {
      return [];
    }
    return game.validMoves.filter(
      (move) =>
        move.from.row === selectedSquare.row && move.from.col === selectedSquare.col
    );
  }, [game, selectedSquare]);

  const initializeGame = async (boardSize = 8) => {
    setLoading(true);
    setError("");

    try {
      const created = await createGame({ boardSize, rules: [], customPieces: [] });
      setGame(created);
      setSelectedSquare(null);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    initializeGame();
  }, []);

  useEffect(() => {
    if (!game?.id) {
      return undefined;
    }

    const websocket = new WebSocket(getWebSocketUrl(game.id));
    websocket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.id === game.id) {
          setGame(payload);
        }
      } catch {
        // Ignore non-JSON events.
      }
    };

    return () => {
      websocket.close();
    };
  }, [game?.id]);

  const submitMove = async (fromSquare, toSquare) => {
    if (!game?.id) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const updated = await makeMove(game.id, {
        fromRow: fromSquare.row,
        fromCol: fromSquare.col,
        toRow: toSquare.row,
        toCol: toSquare.col,
      });
      setGame(updated);
      setSelectedSquare(null);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSquareClick = (row, col) => {
    if (!game || loading) {
      return;
    }
    if (game.gameStatus === "checkmate" || game.gameStatus === "stalemate") {
      return;
    }

    const clickedPiece = game.board[row][col];

    if (!selectedSquare) {
      if (clickedPiece && clickedPiece.color === game.currentPlayer) {
        setSelectedSquare({ row, col });
      }
      return;
    }

    const isSameSquare = selectedSquare.row === row && selectedSquare.col === col;
    if (isSameSquare) {
      setSelectedSquare(null);
      return;
    }

    const chosenMove = selectedMoves.find(
      (move) => move.to.row === row && move.to.col === col
    );

    if (chosenMove) {
      submitMove(selectedSquare, { row, col });
      return;
    }

    if (clickedPiece && clickedPiece.color === game.currentPlayer) {
      setSelectedSquare({ row, col });
      return;
    }

    setSelectedSquare(null);
  };

  const handleReset = async () => {
    if (!game?.id) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const updated = await resetGame(game.id, { boardSize: game.boardSize });
      setGame(updated);
      setSelectedSquare(null);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFlipBoard = () => {
    setBoardFlipped((current) => !current);
  };

  const applyBasicCustomization = async ({ boardSize, patches }) => {
    if (!game?.id) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      let updated = game;
      if (boardSize !== game.boardSize) {
        updated = await resetGame(game.id, { boardSize });
      }

      updated = await updateRules(updated.id, { rules: patches });
      setGame(updated);
      setSelectedSquare(null);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const applyRuleBuilder = async (payload) => {
    if (!game?.id) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const updated = await updateRules(game.id, payload);
      setGame(updated);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const applyRawRules = async (payload) => {
    if (!game?.id) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const updated = await updateRules(game.id, payload);
      setGame(updated);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const applyPieceCustomization = async (payload) => {
    if (!game?.id) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const updated = await updatePieces(game.id, payload);
      setGame(updated);
      setSelectedSquare(null);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  if (!game) {
    return (
      <div className="app-shell centered">
        <p>{loading ? "Creating game..." : "Unable to create game."}</p>
        {error ? <p className="error">{error}</p> : null}
      </div>
    );
  }

  return (
    <div className="app-shell">
      <TopNav
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onReset={handleReset}
        currentPlayer={game.currentPlayer}
        gameStatus={game.gameStatus}
        winner={game.winner}
        onFlipBoard={handleFlipBoard}
        boardFlipped={boardFlipped}
      />

      {error ? <p className="global-error">{error}</p> : null}
      {loading ? <p className="global-loading">Syncing...</p> : null}

      {activeTab === "play" ? (
        <PlayPage
          game={game}
          selectedSquare={selectedSquare}
          onSquareClick={handleSquareClick}
          boardFlipped={boardFlipped}
        />
      ) : (
        <CustomizePage
          game={game}
          onApplyBasic={applyBasicCustomization}
          onApplyPieceCustomization={applyPieceCustomization}
          onApplyRuleBuilder={applyRuleBuilder}
          onApplyRaw={applyRawRules}
          onCreateNewGame={initializeGame}
        />
      )}
    </div>
  );
}

export default App;
