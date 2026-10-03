import NewTabIcon from "./NewTabIcon";

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
      {active === "rulebook" ? (
        <span className="site-nav-button active" aria-current="page">
          Rulebook
        </span>
      ) : (
        <a
          className="site-nav-button new-tab-link"
          href="/rulebook"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Open the Chass Rulebook in a new tab"
        >
          Rulebook
          <NewTabIcon />
        </a>
      )}
    </nav>
  );
}

export default LandingNav;
