import { useEffect, useState } from "react";
import AppLink from "./AppLink";
import { lastPlayedLabel, lastPlayedTimestamp, recentGameLabel } from "../recentGames";

const DESKTOP = "(min-width: 1100px)";

export default function RecentGames({ games }) {
  const [pageSize, setPageSize] = useState(() => typeof window === "undefined" || window.matchMedia(DESKTOP).matches ? 3 : 1);
  const [page, setPage] = useState(0);
  useEffect(() => {
    const media = window.matchMedia(DESKTOP);
    const update = () => { setPageSize(media.matches ? 3 : 1); setPage(0); };
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  if (!games.length) return null;
  const lastPage = Math.ceil(games.length / pageSize) - 1;
  const currentPage = Math.min(page, lastPage);
  const start = currentPage * pageSize;
  const shown = games.slice(start, start + pageSize);
  const paged = games.length > pageSize;
  return (
    <section className="resume-games" aria-labelledby="resume-games-title">
      <header className="resume-games-header">
        <h2 id="resume-games-title">Continue a game</h2>
        <span aria-live="polite">{start + 1}-{start + shown.length} of {games.length}</span>
      </header>
      <div className={`resume-carousel${paged ? " is-paged" : ""}`}>
        {paged && <button className="resume-carousel-arrow" aria-label="Previous saved games" aria-controls="resume-games-list" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 5-7 7 7 7" /></svg>
        </button>}
        <ul id="resume-games-list" style={{ "--resume-columns": pageSize }}>
          {shown.map((entry) => (
            <li key={entry.gameId}>
              <AppLink className="resume-game-link" href={`/game/${encodeURIComponent(entry.gameId)}`}>
                <span className="resume-game-details">
                  <strong>{recentGameLabel(entry)}</strong>
                  {entry.summary?.split(" | ").map((part, index, parts) => index === 1 ? null : (
                    <span key={index}>{index === 0 ? parts.slice(0, 2).join(" | ") : part}</span>
                  ))}
                  <span>{lastPlayedLabel(entry.updatedAt)}</span>
                  <time dateTime={new Date(entry.updatedAt).toISOString()}>{lastPlayedTimestamp(entry.updatedAt)}</time>
                </span>
                {entry.recentMoves?.length ? (
                  <span className="resume-game-moves">
                    <span>Last {entry.recentMoves.length === 1 ? "move" : `${entry.recentMoves.length} moves`}</span>
                    {entry.recentMoves.map((move, index) => <span key={index}>{move}</span>)}
                  </span>
                ) : entry.summary ? <span>No moves yet</span> : null}
              </AppLink>
            </li>
          ))}
        </ul>
        {paged && <button className="resume-carousel-arrow" aria-label="Next saved games" aria-controls="resume-games-list" disabled={currentPage === lastPage} onClick={() => setPage(currentPage + 1)}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 7 7-7 7" /></svg>
        </button>}
      </div>
    </section>
  );
}
