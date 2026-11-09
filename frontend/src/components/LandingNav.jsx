import SiteNavLinks from "./SiteNavLinks";

function LandingNav({ active, onHome, onCustomize }) {
  return (
    <nav className="landing-mode-nav" aria-label="Chass sections">
      <SiteNavLinks active={active} onHome={onHome} onCustomize={onCustomize} />
    </nav>
  );
}

export default LandingNav;
