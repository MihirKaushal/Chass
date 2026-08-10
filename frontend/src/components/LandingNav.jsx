function LandingNav({ active, onPlay, onGambit }) {
  return (
    <nav className="landing-mode-nav" aria-label="Choose a Chass mode">
      <button
        type="button"
        className={active === "play" ? "active" : ""}
        onClick={onPlay}
      >
        Play
      </button>
      <button
        type="button"
        className={active === "gambit" ? "active" : ""}
        onClick={onGambit}
      >
        Chass Gambit
      </button>
    </nav>
  );
}

export default LandingNav;
