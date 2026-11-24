import { useEffect, useState } from "react";

import PageHeading from "../components/PageHeading";
import { getCatalog } from "../api/gameApi";
import { availableBotProfiles, buildClassicBotRequest } from "../botGame";
import BotSetupDialog from "../components/BotSetupDialog";
import LandingNav from "../components/LandingNav";
import PageSkeleton from "../components/PageSkeleton";
import SiteFooter from "../components/SiteFooter";
import Button from "../components/ui/Button";
import ScannerFeatureCard from "../components/scanner/ScannerFeatureCard";
import AppLink from "../components/AppLink";
import {
  browserLocalStorage,
  lastPlayedLabel,
  lastPlayedTimestamp,
  recentGameLabel,
  resumableGames,
} from "../recentGames";
import { SITE_TITLE } from "../documentTitle";
import useDocumentTitle from "../hooks/useDocumentTitle";


function RoomIcon({ type }) {
  if (type === "local") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <rect x="3" y="4" width="18" height="13" rx="2" />
        <path d="M8 21h8M12 17v4" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c2.4 2.5 3.7 5.5 3.7 9S14.4 18.5 12 21M12 3C9.6 5.5 8.3 8.5 8.3 12s1.3 6.5 3.7 9" />
    </svg>
  );
}

function HomePage({ onCreate, onCustomize, onJoinCode }) {
  const [creatingMode, setCreatingMode] = useState("");
  const [showCodeEntry, setShowCodeEntry] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState("");
  const [catalog, setCatalog] = useState(null);
  const [showBotSetup, setShowBotSetup] = useState(false);
  const [resumable] = useState(() => resumableGames(browserLocalStorage()));
  useDocumentTitle(SITE_TITLE);

  useEffect(() => {
    getCatalog().then(setCatalog).catch(() => {});
  }, []);

  const start = async (mode) => {
    setCreatingMode(mode);
    setError("");
    try {
      await onCreate(mode);
    } catch (requestError) {
      setError(requestError.message);
      setCreatingMode("");
    }
  };

  const joinWithCode = (event) => {
    event.preventDefault();
    const normalized = inviteCode.replace(/[^a-z0-9]/gi, "").toUpperCase();
    if (normalized.length !== 8) {
      setError("Enter the eight-character invite code.");
      return;
    }
    setError("");
    onJoinCode(normalized);
  };

  const startBot = async (selection) => {
    setCreatingMode("bot");
    setError("");
    try {
      await onCreate(buildClassicBotRequest(selection));
    } catch (requestError) {
      setError(requestError.message);
      setCreatingMode("");
    }
  };

  if (creatingMode) return <PageSkeleton variant="play" />;

  return (
    <div className="page-frame home-page">
      <main className="landing-shell">
        <section className="landing-hero">
          <LandingNav active="home" onHome={() => {}} onCustomize={onCustomize} />
          <div className="landing-brand-mark" aria-hidden="true">
            <img src="/chass-mark.svg" alt="" />
          </div>
          <PageHeading
            className="landing-copy"
            brand
            title="Chass!"
            tagline="Build the rules. Play the board."
            description="Choose how your opponent is joining:"
          />

          <div className="mode-choice-grid">
            <article className="mode-choice-card">
              <header className="mode-choice-heading">
                <span className="mode-choice-icon"><RoomIcon type="local" /></span>
                <h2>Local room</h2>
              </header>
              <p>Pass one screen between players, or play a bot.</p>
              <div className="mode-choice-actions">
                <Button
                  disabled={Boolean(creatingMode)}
                  loading={creatingMode === "local"}
                  loadingLabel="Preparing board..."
                  onClick={() => start("local")}
                >
                  Start local game
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => {
                    setShowBotSetup(true);
                    setError("");
                  }}
                >
                  Play against a bot
                </Button>
              </div>
            </article>

            <article className="mode-choice-card">
              <header className="mode-choice-heading">
                <span className="mode-choice-icon"><RoomIcon type="online" /></span>
                <h2>Online room</h2>
              </header>
              <p>Create a private link and play from two browsers.</p>
              <div className="mode-choice-actions">
                <Button
                  disabled={Boolean(creatingMode)}
                  loading={creatingMode === "online"}
                  loadingLabel="Opening room..."
                  onClick={() => start("online")}
                >
                  Create online game
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => {
                    setShowCodeEntry((current) => !current);
                    setError("");
                  }}
                >
                  Enter invite code
                </Button>
              </div>
              {showCodeEntry ? (
                <form className="invite-code-form" onSubmit={joinWithCode}>
                  <label htmlFor="invite-code">Invite code</label>
                  <div>
                    <input
                      id="invite-code"
                      type="text"
                      value={inviteCode}
                      autoFocus
                      autoComplete="off"
                      inputMode="text"
                      maxLength="9"
                      placeholder="ABCD1234"
                      onChange={(event) => setInviteCode(
                        event.target.value.replace(/[^a-z0-9-]/gi, "").toUpperCase()
                      )}
                    />
                    <Button type="submit">Join game</Button>
                  </div>
                </form>
              ) : null}
            </article>
          </div>

          {resumable.length ? (
            <section className="resume-games" aria-labelledby="resume-games-title">
              <h2 id="resume-games-title">Continue a game</h2>
              <ul>
                {resumable.map((entry) => (
                  <li key={entry.gameId}>
                    <AppLink className="resume-game-link" href={`/game/${encodeURIComponent(entry.gameId)}`}>
                      <span className="resume-game-details">
                        <strong>{recentGameLabel(entry)}</strong>
                        {entry.summary ? <span className="resume-game-summary">{entry.summary}</span> : null}
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
            </section>
          ) : null}

          <ScannerFeatureCard />
          {error ? <p className="landing-error">{error}</p> : null}
        </section>
      </main>
      <SiteFooter />
      <BotSetupDialog
        open={showBotSetup}
        profiles={availableBotProfiles(catalog, "stockfish")}
        loading={creatingMode === "bot"}
        error={error}
        onClose={() => setShowBotSetup(false)}
        onStart={startBot}
      />
    </div>
  );
}

export default HomePage;
