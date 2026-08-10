import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  completeGambitHandoff,
  createGame,
  getGame,
  joinGame,
  makeMove,
  readyGambitDeployment,
  replaceInvite,
  resetGame,
  updateBoardLayout,
  updateGambitDeployment,
  updatePieces,
  updateRules,
  useGambitPower,
} from "./api/gameApi";
import OnlineLobby from "./components/OnlineLobby";
import TopNav from "./components/TopNav";
import {
  createInviteUrl,
  loadGameSession,
  saveGameSession,
  updateGameSession,
} from "./gameSession";
import useGameSocket from "./hooks/useGameSocket";
import CustomizePage from "./pages/CustomizePage";
import GambitHomePage from "./pages/GambitHomePage";
import GambitPage from "./pages/GambitPage";
import HomePage from "./pages/HomePage";
import JoinPage from "./pages/JoinPage";
import PlayPage from "./pages/PlayPage";
import { navigate, useRoute } from "./routing";


const FINISHED_STATUSES = new Set(["checkmate", "stalemate", "score_target"]);

function colorLabel(color) {
  return color ? color.charAt(0).toUpperCase() + color.slice(1) : "";
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

  return winner ? `${winnerLabel} won!` : "Game over.";
}

function sessionFromResponse(response) {
  const inviteUrl = response.inviteToken
    ? createInviteUrl(response.inviteToken)
    : response.inviteUrl || null;

  return {
    gameId: response.game.id,
    mode: response.game.mode,
    variant: response.game.variant,
    token: response.playerToken,
    color: response.playerColor,
    role: response.role,
    inviteToken: response.inviteToken,
    inviteUrl,
    inviteExpiresAt: response.inviteExpiresAt,
  };
}

function GameWorkspace({ gameId }) {
  const [session, setSession] = useState(() => loadGameSession(gameId));
  const [game, setGame] = useState(null);
  const gameRef = useRef(null);
  const [activeTab, setActiveTab] = useState("play");
  const [selectedSquare, setSelectedSquare] = useState(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");
  const [socketMessage, setSocketMessage] = useState("");
  const [presence, setPresence] = useState({ white: false, black: false });
  const [boardFlipped, setBoardFlipped] = useState(
    session?.mode === "online" && session?.color === "black"
  );
  const [autoBoardFlipEnabled, setAutoBoardFlipEnabled] = useState(
    session?.mode !== "online"
  );
  const [endgameMessage, setEndgameMessage] = useState("");
  const [showEndgameModal, setShowEndgameModal] = useState(false);
  const lastEndgameSignatureRef = useRef("");
  const moveTrackerRef = useRef({ gameId: "", moveCount: 0 });

  const applyIncomingGame = useCallback(
    (incoming) => {
      if (!incoming || incoming.id !== gameId) {
        return;
      }

      const current = gameRef.current;
      if (current && incoming.version < current.version) {
        return;
      }

      gameRef.current = incoming;
      setGame(incoming);
      setInitialLoading(false);
    },
    [gameId]
  );

  const refreshGame = useCallback(async () => {
    const latest = await getGame(gameId, session?.token);
    applyIncomingGame(latest);

    if (!session && latest.mode === "local") {
      const localSession = {
        gameId,
        mode: "local",
        role: "local",
        token: null,
        color: null,
      };
      saveGameSession(gameId, localSession);
      setSession(localSession);
    }

    return latest;
  }, [applyIncomingGame, gameId, session]);

  useEffect(() => {
    let cancelled = false;
    setInitialLoading(true);
    setError("");

    getGame(gameId, session?.token)
      .then((latest) => {
        if (cancelled) {
          return;
        }
        applyIncomingGame(latest);
        if (!session && latest.mode === "local") {
          const localSession = {
            gameId,
            mode: "local",
            role: "local",
            token: null,
            color: null,
          };
          saveGameSession(gameId, localSession);
          setSession(localSession);
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError.message);
          setInitialLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [applyIncomingGame, gameId, session?.token]);

  const connectionStatus = useGameSocket({
    gameId,
    token: session?.token,
    enabled: Boolean(game),
    onGame: applyIncomingGame,
    onPresence: (payload) => setPresence(payload.connected || { white: false, black: false }),
    onEvent: (payload) => {
      if (payload.type === "player_joined") {
        setSocketMessage(`${colorLabel(payload.color)} joined the game.`);
      }
    },
    onError: setSocketMessage,
  });

  const selectedMoves = useMemo(() => {
    if (!game || !selectedSquare) {
      return [];
    }
    return game.validMoves.filter(
      (move) =>
        move.from.row === selectedSquare.row && move.from.col === selectedSquare.col
    );
  }, [game, selectedSquare]);

  const canCustomize =
    game?.variant !== "gambit" &&
    (game?.mode === "local" || (game?.mode === "online" && session?.role === "host"));
  const canMove =
    Boolean(game?.ready) &&
    game?.phase === "play" &&
    (game?.mode === "local" || session?.color === game?.currentPlayer) &&
    !FINISHED_STATUSES.has(game?.gameStatus) &&
    !game?.winner;

  useEffect(() => {
    if (!canCustomize && activeTab === "customize") {
      setActiveTab("play");
    }
  }, [activeTab, canCustomize]);

  useEffect(() => {
    setSelectedSquare(null);
  }, [game?.version]);

  useEffect(() => {
    if (game?.mode !== "online" || !session?.color) {
      return;
    }

    setAutoBoardFlipEnabled(false);
    setBoardFlipped(session.color === "black");
  }, [game?.id, game?.mode, session?.color]);

  useEffect(() => {
    if (game?.variant !== "gambit" || game.phase !== "deployment") {
      return;
    }
    const setupColor = game.gambit?.editableColor || game.gambit?.viewerColor;
    if (setupColor) {
      setBoardFlipped(setupColor === "black");
    }
  }, [game?.gambit?.editableColor, game?.gambit?.viewerColor, game?.phase, game?.variant]);

  useEffect(() => {
    if (
      game?.variant === "gambit" &&
      game.phase === "play" &&
      game.history.length === 0
    ) {
      setBoardFlipped(game.mode === "online" ? session?.color === "black" : false);
      setAutoBoardFlipEnabled(game.mode !== "online");
    }
  }, [game?.history?.length, game?.mode, game?.phase, game?.variant, session?.color]);

  useEffect(() => {
    if (!socketMessage) {
      return undefined;
    }
    const timer = window.setTimeout(() => setSocketMessage(""), 4500);
    return () => window.clearTimeout(timer);
  }, [socketMessage]);

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
      setBoardFlipped(game.currentPlayer === "black");
    }
    moveTrackerRef.current = { gameId: game.id, moveCount };
  }, [autoBoardFlipEnabled, game?.id, game?.history?.length]);

  const runAction = async (operation) => {
    setActionLoading(true);
    setError("");
    try {
      return await operation();
    } catch (requestError) {
      setError(requestError.message);
      if (requestError instanceof ApiError && requestError.status === 409) {
        await refreshGame().catch(() => {});
      }
      throw requestError;
    } finally {
      setActionLoading(false);
    }
  };

  const mutate = async (apiFunction, payload) => {
    const current = gameRef.current;
    if (!current) {
      throw new Error("Game state is not loaded yet.");
    }

    const updated = await apiFunction(
      gameId,
      { ...payload, expectedVersion: current.version },
      session?.token
    );
    applyIncomingGame(updated);
    return updated;
  };

  const submitMove = async (fromSquare, toSquare) => {
    try {
      await runAction(() =>
        mutate(makeMove, {
          fromRow: fromSquare.row,
          fromCol: fromSquare.col,
          toRow: toSquare.row,
          toCol: toSquare.col,
        })
      );
    } catch {
      // The shared error banner explains rejected moves.
    }
  };

  const handleDeploymentChange = async (payload) => {
    try {
      await runAction(() => mutate(updateGambitDeployment, payload));
    } catch {
      // The shared error banner explains rejected deployment changes.
    }
  };

  const handleGambitReady = async () => {
    try {
      await runAction(() => mutate(readyGambitDeployment, {}));
    } catch {
      // The shared error banner explains why the army cannot lock in yet.
    }
  };

  const handleGambitHandoff = async () => {
    try {
      await runAction(() => mutate(completeGambitHandoff, {}));
    } catch {
      // The shared error banner explains handoff failures.
    }
  };

  const handleGambitPower = async (payload) => {
    try {
      await runAction(() => mutate(useGambitPower, payload));
    } catch {
      // The shared error banner explains rejected command actions.
    }
  };

  const handleSquareClick = (row, col) => {
    if (!game || actionLoading || !canMove) {
      return;
    }

    const clickedPiece = game.board[row][col];
    if (!selectedSquare) {
      if (clickedPiece && clickedPiece.color === game.currentPlayer) {
        setSelectedSquare({ row, col });
      }
      return;
    }

    if (selectedSquare.row === row && selectedSquare.col === col) {
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
    } else {
      setSelectedSquare(null);
    }
  };

  const handleReset = async () => {
    try {
      await runAction(() =>
        mutate(resetGame, {
          boardRows: game.boardRows ?? game.boardSize,
          boardCols: game.boardCols ?? game.boardSize,
        })
      );
      setBoardFlipped(false);
    } catch {
      // The shared error banner explains reset failures.
    }
  };

  const applyBasicCustomization = async ({ boardRows, boardCols, patches }) =>
    runAction(async () => {
      let current = gameRef.current;
      const currentRows = current.boardRows ?? current.boardSize;
      const currentCols = current.boardCols ?? current.boardSize;

      if (boardRows !== currentRows || boardCols !== currentCols) {
        current = await mutate(resetGame, { boardRows, boardCols });
        setBoardFlipped(false);
      }

      return mutate(updateRules, { rules: patches });
    });

  const applyBoardLayoutCustomization = ({ boardRows, boardCols, placements }) =>
    runAction(() =>
      mutate(updateBoardLayout, {
        boardRows,
        boardCols,
        placements,
      })
    );

  const applyRuleBuilder = (payload) =>
    runAction(() => mutate(updateRules, payload));

  const applyPieceCustomization = (payload) =>
    runAction(() => mutate(updatePieces, payload));

  const createReplacementGame = async (dimensions) => {
    const response = await runAction(() =>
      createGame({
        mode: game.mode,
        boardRows: dimensions.boardRows,
        boardCols: dimensions.boardCols,
        rules: [],
        customPieces: [],
      })
    );
    const nextSession = sessionFromResponse(response);
    saveGameSession(response.game.id, nextSession);
    navigate(`/game/${response.game.id}`);
  };

  const handleReplaceInvite = async () => {
    try {
      const invite = await runAction(() => replaceInvite(gameId, session?.token));
      const updatedSession = updateGameSession(gameId, {
        inviteToken: invite.inviteToken,
        inviteUrl: createInviteUrl(invite.inviteToken),
        inviteExpiresAt: invite.inviteExpiresAt,
      });
      setSession(updatedSession);
    } catch {
      // The shared error banner explains invite failures.
    }
  };

  if (initialLoading && !game) {
    return (
      <div className="app-shell centered">
        <div className="loading-card">
          <span className="loading-mark" />
          <h1>Loading the board</h1>
          <p>Free hosts may need a moment to wake up.</p>
        </div>
      </div>
    );
  }

  if (!game) {
    return (
      <div className="app-shell centered">
        <div className="loading-card">
          <h1>Game unavailable</h1>
          <p>{error || "This game could not be loaded."}</p>
          <div className="button-row">
            <button type="button" onClick={() => window.location.reload()}>
              Try Again
            </button>
            <button type="button" className="secondary" onClick={() => navigate("/")}>
              Back Home
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <TopNav
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onReset={handleReset}
        onHome={() => navigate("/")}
        currentPlayer={game.currentPlayer}
        gameStatus={game.gameStatus}
        winner={game.winner}
        onFlipBoard={() => setBoardFlipped((current) => !current)}
        onToggleAutoBoardFlip={() => setAutoBoardFlipEnabled((current) => !current)}
        boardFlipped={boardFlipped}
        autoBoardFlipEnabled={autoBoardFlipEnabled}
        canCustomize={canCustomize}
        canReset={canCustomize}
        mode={game.mode}
        playerColor={session?.color}
        connectionStatus={connectionStatus}
        variant={game.variant}
        phase={game.phase}
        onOpenGambit={() => navigate("/gambit")}
      />

      {game.mode === "online" ? (
        <OnlineLobby
          game={game}
          session={session}
          presence={presence}
          connectionStatus={connectionStatus}
          onReplaceInvite={handleReplaceInvite}
        />
      ) : null}

      {error ? <p className="global-error">{error}</p> : null}
      {socketMessage ? <p className="sync-message">{socketMessage}</p> : null}
      {actionLoading ? <p className="global-loading">Syncing authoritative game state...</p> : null}
      {!canMove &&
      game.ready &&
      game.mode === "online" &&
      game.phase === "play" &&
      activeTab === "play" &&
      !game.winner ? (
        <p className="turn-notice">
          You are {colorLabel(session?.color)}. Waiting for {colorLabel(game.currentPlayer)} to
          move.
        </p>
      ) : null}

      {game.variant === "gambit" ? (
        <GambitPage
          game={game}
          selectedSquare={selectedSquare}
          onSquareClick={handleSquareClick}
          boardFlipped={boardFlipped}
          interactive={canMove && !actionLoading}
          actionLoading={actionLoading}
          onDeploymentChange={handleDeploymentChange}
          onReady={handleGambitReady}
          onHandoff={handleGambitHandoff}
          onPower={handleGambitPower}
        />
      ) : activeTab === "play" ? (
        <PlayPage
          game={game}
          selectedSquare={selectedSquare}
          onSquareClick={handleSquareClick}
          boardFlipped={boardFlipped}
          interactive={canMove && !actionLoading}
        />
      ) : (
        <CustomizePage
          game={game}
          onApplyBasic={applyBasicCustomization}
          onApplyBoardLayout={applyBoardLayoutCustomization}
          onApplyPieceCustomization={applyPieceCustomization}
          onApplyRuleBuilder={applyRuleBuilder}
          onApplyRaw={applyRuleBuilder}
          onCreateNewGame={createReplacementGame}
        />
      )}

      {showEndgameModal ? (
        <div className="endgame-modal-backdrop" role="presentation">
          <div className="endgame-modal" role="dialog" aria-modal="true" aria-live="polite">
            <span className="eyebrow">Final position</span>
            <h2>Match Finished</h2>
            <p>{endgameMessage}</p>
            <div className="button-row">
              {canCustomize ? (
                <button type="button" onClick={handleReset}>
                  Play Again
                </button>
              ) : null}
              <button
                type="button"
                className="secondary"
                onClick={() => setShowEndgameModal(false)}
              >
                Review Board
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function App() {
  const route = useRoute();

  const handleCreate = async (mode, variant = "classic") => {
    const response = await createGame({
      mode,
      variant,
      boardRows: 8,
      boardCols: 8,
      rules: [],
      customPieces: [],
    });
    const session = sessionFromResponse(response);
    saveGameSession(response.game.id, session);
    navigate(`/game/${response.game.id}`);
  };

  const handleJoin = async (inviteToken) => {
    const response = await joinGame(inviteToken);
    const session = sessionFromResponse(response);
    saveGameSession(response.game.id, session);
    navigate(`/game/${response.game.id}`, { replace: true });
  };

  if (route.name === "join") {
    return (
      <JoinPage
        inviteToken={route.inviteToken}
        onJoin={handleJoin}
        onHome={() => navigate("/")}
      />
    );
  }

  if (route.name === "game") {
    return <GameWorkspace key={route.gameId} gameId={route.gameId} />;
  }

  if (route.name === "gambit") {
    return (
      <GambitHomePage
        onCreate={(mode) => handleCreate(mode, "gambit")}
        onOpenClassic={() => navigate("/")}
      />
    );
  }

  return <HomePage onCreate={handleCreate} onOpenGambit={() => navigate("/gambit")} />;
}

export default App;
