function LandingNav({ active, onHome, onCustomize }) {
  return (
    <nav className="landing-mode-nav" aria-label="Chass sections">
      <button
        type="button"
        className={`site-nav-button${active === "home" ? " active" : ""}`}
        aria-current={active === "home" ? "page" : undefined}
        onClick={onHome}
      >
        Home
      </button>
      <button
        type="button"
        className={`site-nav-button${active === "customize" ? " active" : ""}`}
        aria-current={active === "customize" ? "page" : undefined}
        onClick={onCustomize}
      >
        Customize
      </button>
    </nav>
  );
}

export default LandingNav;
