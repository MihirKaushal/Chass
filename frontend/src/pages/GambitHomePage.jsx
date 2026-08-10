import { useState } from "react";

import LandingNav from "../components/LandingNav";


function GambitHomePage({ onCreate, onOpenClassic }) {
  const [creatingMode, setCreatingMode] = useState("");
  const [error, setError] = useState("");

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

  return (
    <main className="landing-shell gambit-landing-shell">
      <section className="landing-hero gambit-hero">
        <LandingNav
          active="gambit"
          onPlay={onOpenClassic}
          onGambit={() => {}}
        />

        <div className="gambit-hero-grid">
          <div className="landing-copy">
            <span className="eyebrow">Hidden armies. Contested center. One King.</span>
            <h1>Chass Gambit</h1>
            <p>
              Build a private army from a 39-point War Chest, then fight for the four
              affinity squares to unlock command powers during the match.
            </p>
          </div>

          <aside className="gambit-rule-card" aria-label="Chass Gambit rules summary">
            <span className="gambit-rule-number">39</span>
            <strong>points to shape your opening</strong>
            <div className="gambit-rule-strip">
              <span>1 King</span>
              <span>16 pieces max</span>
              <span>2 hidden ranks</span>
            </div>
          </aside>
        </div>

        <div className="mode-choice-grid gambit-mode-grid">
          <article className="mode-choice-card">
            <span className="mode-number">HOT SEAT</span>
            <h2>Private Handoff</h2>
            <p>White builds first, the screen locks, then Black takes over from Black's view.</p>
            <ul>
              <li>Full-screen privacy handoff</li>
              <li>Automatic setup perspective</li>
              <li>No account or internet needed</li>
            </ul>
            <button
              type="button"
              disabled={Boolean(creatingMode)}
              onClick={() => start("local")}
            >
              {creatingMode === "local" ? "Opening War Chest..." : "Start Local Gambit"}
            </button>
          </article>

          <article className="mode-choice-card featured gambit-featured-card">
            <span className="mode-number">ONLINE</span>
            <h2>Secret Deployment</h2>
            <p>Share one private link. The server keeps each army hidden until both are legal.</p>
            <ul>
              <li>Seat-private board responses</li>
              <li>Simultaneous hidden setup</li>
              <li>Live play and reconnection</li>
            </ul>
            <button
              type="button"
              disabled={Boolean(creatingMode)}
              onClick={() => start("online")}
            >
              {creatingMode === "online" ? "Opening Command Room..." : "Create Online Gambit"}
            </button>
          </article>
        </div>

        {error ? <p className="landing-error">{error}</p> : null}
        <p className="landing-footnote">
          White always moves first. Standard check, checkmate, and promotion rules still decide
          the battle.
        </p>
      </section>
    </main>
  );
}

export default GambitHomePage;
