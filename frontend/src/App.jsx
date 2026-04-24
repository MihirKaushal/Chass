import { useEffect, useMemo, useRef, useState } from "react";

import TopNav from "./components/TopNav";
import CustomizePage from "./pages/CustomizePage";
import PlayPage from "./pages/PlayPage";
import {
  createGame,
  getWebSocketUrl,
  makeMove,
  resetGame,
  updateBoardLayout,
  updatePieces,
  updateRules,
} from "./api/gameApi";

const FINISHED_STATUSES = new Set(["checkmate", "stalemate", "score_target"]);

function colorLabel(color) {
  if (!color) {
    return "";
  }
  return color.charAt(0).toUpperCase() + color.slice(1);
}

function oppositeColor(color) {
  if (color === "white") {
    return "black";
  }
  if (color === "black") {
    return "white";
  }
  return "";
}

function findRule(rules, ruleId) {
  return rules.find((rule) => rule.id === ruleId);
}

function buildEndgameMessage(game) {
  const winner = game.winner;
  const winnerLabel = colorLabel(winner);
  const loserLabel = colorLabel(oppositeColor(winner));

  if (game.gameStatus === "checkmate" && winner) {
    return `${winnerLabel} won! ${winnerLabel} checkmated ${loserLabel}'s King.`;
  }

  if (game.gameStatus === "score_target" && winner) {
    const scoreTargetRule = findRule(game.rules, "score_target_win");
    const targetScore = Number(scoreTargetRule?.params?.targetScore ?? 21);
    const normalizedTarget = Number.isFinite(targetScore) ? targetScore : 21;
    return `${winnerLabel} won! ${winnerLabel} got to ${normalizedTarget} points.`;
  }

  if (game.gameStatus === "stalemate") {
    return "Stalemate! Neither side has a legal move.";
  }

  if (winner) {
    return `${winnerLabel} won!`;
  }

  return "Game over.";
}

function App() {
  const [activeTab, setActiveTab] = useState("play");
  const [game, setGame] = useState(null);
  const [selectedSquare, setSelectedSquare] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [boardFlipped, setBoardFlipped] = useState(false);
  const [autoBoardFlipEnabled, setAutoBoardFlipEnabled] = useState(true);
  const [endgameMessage, setEndgameMessage] = useState("");
  const [showEndgameModal, setShowEndgameModal] = useState(false);
  const lastEndgameSignatureRef = useRef("");
  const moveTrackerRef = useRef({ gameId: "", moveCount: 0 });

  const selectedMoves = useMemo(() => {
    if (!game || !selectedSquare) {
      return [];
    }
    return game.validMoves.filter(
      (move) =>
        move.from.row === selectedSquare.row && move.from.col === selectedSquare.col
    );
  }, [game, selectedSquare]);

  const initializeGame = async (dimensions = { boardRows: 8, boardCols: 8 }) => {
    setLoading(true);
    setError("");

    const normalized =
      typeof dimensions === "number"
        ? { boardRows: dimensions, boardCols: dimensions }
        : dimensions;

    try {
      const created = await createGame({
        boardRows: normalized.boardRows,
        boardCols: normalized.boardCols,
        rules: [],
        customPieces: [],
      });
      setGame(created);
      setSelectedSquare(null);
      setBoardFlipped(false);
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

  useEffect(() => {
    if (!game) {
      return;
    }

    const gameEnded = FINISHED_STATUSES.has(game.gameStatus) || Boolean(game.winner);
    if (!gameEnded) {
      setShowEndgameModal(false);
      setEndgameMessage("");
      lastEndgameSignatureRef.current = "";
      return;
    }

    const signature = [
      game.id,
      game.gameStatus,
      game.winner ?? "none",
      game.history.length,
    ].join(":");

    if (lastEndgameSignatureRef.current === signature) {
      return;
    }

    lastEndgameSignatureRef.current = signature;
    setEndgameMessage(buildEndgameMessage(game));
    setShowEndgameModal(true);
  }, [game]);

  useEffect(() => {
    if (!game?.id) {
      return;
    }

    const moveCount = game.history?.length ?? 0;
    const tracker = moveTrackerRef.current;

    if (tracker.gameId !== game.id) {
      moveTrackerRef.current = { gameId: game.id, moveCount };
      return;
    }

    const diff = moveCount - tracker.moveCount;
    if (autoBoardFlipEnabled && diff > 0 && diff % 2 === 1) {
      setBoardFlipped((current) => !current);
    }

    moveTrackerRef.current = { gameId: game.id, moveCount };
  }, [autoBoardFlipEnabled, game?.id, game?.history?.length]);

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
    if (FINISHED_STATUSES.has(game.gameStatus) || game.winner) {
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
      const updated = await resetGame(game.id, {
        boardRows: game.boardRows ?? game.boardSize,
        boardCols: game.boardCols ?? game.boardSize,
      });
      setGame(updated);
      setSelectedSquare(null);
      setBoardFlipped(false);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFlipBoard = () => {
    setBoardFlipped((current) => !current);
  };

  const handleToggleAutoBoardFlip = () => {
    setAutoBoardFlipEnabled((current) => !current);
  };

  const applyBasicCustomization = async ({ boardRows, boardCols, patches }) => {
    if (!game?.id) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      let updated = game;
      const currentRows = game.boardRows ?? game.boardSize;
      const currentCols = game.boardCols ?? game.boardSize;
      if (boardRows !== currentRows || boardCols !== currentCols) {
        updated = await resetGame(game.id, { boardRows, boardCols });
        setBoardFlipped(false);
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

  const applyBoardLayoutCustomization = async ({ boardRows, boardCols, placements }) => {
    if (!game?.id) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const updated = await updateBoardLayout(game.id, {
        boardRows,
        boardCols,
        placements,
      });
      setGame(updated);
      setSelectedSquare(null);
      setBoardFlipped(false);
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
        onToggleAutoBoardFlip={handleToggleAutoBoardFlip}
        boardFlipped={boardFlipped}
        autoBoardFlipEnabled={autoBoardFlipEnabled}
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
          onApplyBoardLayout={applyBoardLayoutCustomization}
          onApplyPieceCustomization={applyPieceCustomization}
          onApplyRuleBuilder={applyRuleBuilder}
          onApplyRaw={applyRawRules}
          onCreateNewGame={initializeGame}
        />
      )}

      {showEndgameModal ? (
        <div className="endgame-modal-backdrop" role="presentation">
          <div className="endgame-modal" role="dialog" aria-modal="true" aria-live="polite">
            <h2>Match Finished</h2>
            <p>{endgameMessage}</p>
            <button type="button" onClick={() => setShowEndgameModal(false)}>
              Close
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default App;
