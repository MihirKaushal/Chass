import { useEffect, useState } from "react";
import { preferenceSeat, readGamePreferences, saveGamePreferences } from "../gamePreferences";
import { browserLocalStorage } from "../recentGames";

export default function useGamePreferences(gameId, game, session) {
  const context = {
    gameId,
    mode: game?.mode || session?.mode || "local",
    color: session?.color || game?.bot?.humanColor || null,
  };
  const key = preferenceSeat(context);
  const [saved, setSaved] = useState(() => ({ key, ...readGamePreferences(browserLocalStorage(), context) }));
  // Mode/seat may arrive after the initial request. Never overwrite stored
  // preferences with temporary defaults while the game is loading.
  const preferences = saved.key === key ? saved : { key, ...readGamePreferences(browserLocalStorage(), context) };
  const [boardFlipped, setBoardFlipped] = useState(preferences.flipped);

  useEffect(() => {
    setBoardFlipped(readGamePreferences(browserLocalStorage(), context).flipped);
  }, [key, game?.phase]);

  useEffect(() => {
    if (game?.phase === "play" && preferences.autoFlip) {
      setBoardFlipped(game.currentPlayer === "black");
    }
  }, [key, game?.phase, game?.currentPlayer, game?.historyPagination?.epoch, preferences.autoFlip]);

  const update = (patch) => {
    const next = { ...preferences, flipped: boardFlipped, ...patch };
    setSaved(next);
    saveGamePreferences(browserLocalStorage(), context, next);
  };
  return {
    boardFlipped, setBoardFlipped,
    autoBoardFlipEnabled: preferences.autoFlip,
    matchAnalysisEnabled: preferences.analysis,
    flipBoard: () => {
      update({ flipped: !boardFlipped });
      setBoardFlipped(!boardFlipped);
    },
    toggleAutoFlip: () => update({ autoFlip: !preferences.autoFlip }),
    toggleAnalysis: () => update({ analysis: !preferences.analysis }),
  };
}
