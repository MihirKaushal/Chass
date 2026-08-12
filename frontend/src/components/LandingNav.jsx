function LandingNav({ active, onPlay, onCustomize }) {
  return (
    <nav className="landing-mode-nav" aria-label="Chass sections">
      <button type="button" className={active === "play" ? "active" : ""} onClick={onPlay}>
        Play
      </button>
      <button
        type="button"
        className={active === "customize" ? "active" : ""}
        onClick={onCustomize}
      >
        Customize
      </button>
    </nav>
  );
}

export default LandingNav;
