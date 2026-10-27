import { useEffect, useState } from "react";

import { getCatalog } from "../api/gameApi";
import LandingNav from "../components/LandingNav";
import PageSkeleton from "../components/PageSkeleton";
import RulebookReference from "../components/RulebookReference";
import SiteFooter from "../components/SiteFooter";
import Button from "../components/ui/Button";

function RulebookPage({ onHome, onCustomize }) {
  const [catalog, setCatalog] = useState(null);
  const [error, setError] = useState("");
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    if (!catalog) return undefined;
    let frame;
    const revealSection = () => {
      if (!/^#rulebook-[a-z-]+$/.test(window.location.hash)) return;
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        document.getElementById(window.location.hash.slice(1))?.scrollIntoView({
          block: "start",
        });
      });
    };
    revealSection();
    window.addEventListener("popstate", revealSection);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("popstate", revealSection);
    };
  }, [catalog]);

  useEffect(() => {
    let active = true;
    setError("");
    getCatalog()
      .then((result) => {
        if (active) setCatalog(result);
      })
      .catch(() => {
        if (active) setError("The Rulebook could not load. Check the connection and try again.");
      });
    return () => {
      active = false;
    };
  }, [retryKey]);

  return (
    <div className="page-frame">
      <main className="rulebook-page-shell">
        <LandingNav active="rulebook" onHome={onHome} onCustomize={onCustomize} />
        {catalog ? <RulebookReference catalog={catalog} /> : null}
        {!catalog && !error ? <PageSkeleton variant="rulebook" embedded /> : null}
        {error ? (
          <section className="rulebook-load-error" role="alert">
            <span className="eyebrow">Reference Unavailable</span>
            <h1>We could not load the Rulebook.</h1>
            <p>{error}</p>
            <Button onClick={() => setRetryKey((current) => current + 1)}>Try Again</Button>
          </section>
        ) : null}
      </main>
      <SiteFooter />
    </div>
  );
}

export default RulebookPage;
