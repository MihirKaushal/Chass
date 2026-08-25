import { useEffect, useState } from "react";

import { getCatalog } from "../api/gameApi";
import LandingNav from "../components/LandingNav";
import PageSkeleton from "../components/PageSkeleton";
import SiteFooter from "../components/SiteFooter";
import Button from "../components/ui/Button";


function HomePage({ onCreate, onCustomize, onJoinCode }) {
  const [creatingMode, setCreatingMode] = useState("");
  const [showCodeEntry, setShowCodeEntry] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getCatalog().catch(() => {});
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
              <h2>Same Device</h2>
              <p>Pass one screen between players. No account or invite required.</p>
              <Button
                disabled={Boolean(creatingMode)}
                loading={creatingMode === "local"}
                loadingLabel="Preparing Board..."
                onClick={() => start("local")}
              >
                Start Local Game
              </Button>
            </article>

            <article className="mode-choice-card featured">
              <h2>Invite a Friend</h2>
              <p>Create a private link and play from two browsers, anywhere.</p>
              <Button
                disabled={Boolean(creatingMode)}
                loading={creatingMode === "online"}
                loadingLabel="Opening Room..."
                onClick={() => start("online")}
              >
                Create Online Game
              </Button>
            </article>
          </div>

          <div className="join-code-entry">
            <Button
              variant="secondary"
              className="join-code-toggle"
              onClick={() => {
                setShowCodeEntry((current) => !current);
                setError("");
              }}
            >
              Enter Invite Code
            </Button>
            {showCodeEntry ? (
              <form onSubmit={joinWithCode}>
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
          </div>

          {error ? <p className="landing-error">{error}</p> : null}
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

export default HomePage;
