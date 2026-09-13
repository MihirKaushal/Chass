import { useEffect, useState } from "react";

import { getCatalog } from "../api/gameApi";
import { availableBotProfiles, buildClassicBotRequest } from "../botGame";
import BotSetupDialog from "../components/BotSetupDialog";
import LandingNav from "../components/LandingNav";
import PageSkeleton from "../components/PageSkeleton";
import SiteFooter from "../components/SiteFooter";
import Button from "../components/ui/Button";


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
    <div className="page-frame">
      <main className="landing-shell">
        <section className="landing-hero">
          <LandingNav active="home" onHome={() => {}} onCustomize={onCustomize} />
          <div className="landing-brand-mark" aria-hidden="true">
            <img src="/chass-mark.svg" alt="" />
          </div>
          <div className="landing-copy">
            <span className="eyebrow">Build the rules. Play the board.</span>
            <h1>Chass!</h1>
            <p className="landing-intro">
              <span>Classic chess when you want it. A flexible rule laboratory when you do not.</span>
              <span>Choose how your opponent is joining:</span>
            </p>
          </div>

          <div className="mode-choice-grid">
            <article className="mode-choice-card">
              <header className="mode-choice-heading">
                <span className="mode-choice-icon"><RoomIcon type="local" /></span>
                <h2>Local Room</h2>
              </header>
              <p>Pass one screen between players. No invite required.</p>
              <div className="mode-choice-actions">
                <Button
                  disabled={Boolean(creatingMode)}
                  loading={creatingMode === "local"}
                  loadingLabel="Preparing Board..."
                  onClick={() => start("local")}
                >
                  Start Local Game
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => {
                    setShowBotSetup(true);
                    setError("");
                  }}
                >
                  Play Against A Bot
                </Button>
              </div>
            </article>

            <article className="mode-choice-card featured">
              <header className="mode-choice-heading">
                <span className="mode-choice-icon"><RoomIcon type="online" /></span>
                <h2>Online Room</h2>
              </header>
              <p>Create a private link and play from two browsers, anywhere.</p>
              <div className="mode-choice-actions">
                <Button
                  disabled={Boolean(creatingMode)}
                  loading={creatingMode === "online"}
                  loadingLabel="Opening Room..."
                  onClick={() => start("online")}
                >
                  Create Online Game
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => {
                    setShowCodeEntry((current) => !current);
                    setError("");
                  }}
                >
                  Enter Invite Code
                </Button>
              </div>
              {showCodeEntry ? (
                <form className="invite-code-form" onSubmit={joinWithCode}>
                  <label htmlFor="invite-code">Invite Code</label>
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
                    <Button type="submit">Join Game</Button>
                  </div>
                </form>
              ) : null}
            </article>
          </div>

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
