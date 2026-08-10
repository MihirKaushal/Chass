import { useState } from "react";

import LandingNav from "../components/LandingNav";


function HomePage({ onCreate, onOpenGambit }) {
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
    <main className="landing-shell">
      <section className="landing-hero">
        <LandingNav active="play" onPlay={() => {}} onGambit={onOpenGambit} />
        <div className="landing-copy">
          <span className="eyebrow">Build the rules. Play the board.</span>
          <h1>Chass!</h1>
          <p>
            Classic chess when you want it. A flexible rule laboratory when you do not.
            Choose how your opponent is joining.
          </p>
        </div>

        <div className="mode-choice-grid">
          <article className="mode-choice-card">
            <span className="mode-number">01</span>
            <h2>Same Device</h2>
            <p>Pass one screen between players. No account, invite, or connection required.</p>
            <ul>
              <li>Automatic board flipping</li>
              <li>Full customization access</li>
              <li>Fast local setup</li>
            </ul>
            <button
              type="button"
              disabled={Boolean(creatingMode)}
              onClick={() => start("local")}
            >
              {creatingMode === "local" ? "Preparing board..." : "Start Local Game"}
            </button>
          </article>

          <article className="mode-choice-card featured">
            <span className="mode-number">02</span>
            <h2>Invite a Friend</h2>
            <p>Create a private link and play from two browsers, anywhere.</p>
            <ul>
              <li>Private one-use invite</li>
              <li>Live move synchronization</li>
              <li>Automatic reconnection</li>
            </ul>
            <button
              type="button"
              disabled={Boolean(creatingMode)}
              onClick={() => start("online")}
            >
              {creatingMode === "online" ? "Opening room..." : "Create Online Game"}
            </button>
          </article>
        </div>

        {error ? <p className="landing-error">{error}</p> : null}
        <p className="landing-footnote">
          Online games are anonymous. This browser stores your private player seat so you can
          reconnect.
        </p>
      </section>
    </main>
  );
}

export default HomePage;
