import { useEffect } from "react";

import catalog from "../generated/rulebookCatalog.json";
import LandingNav from "../components/LandingNav";
import RulebookReference from "../components/RulebookReference";
import SiteFooter from "../components/SiteFooter";
import { pageTitle } from "../documentTitle";
import useDocumentTitle from "../hooks/useDocumentTitle";

function RulebookPage({ onHome, onCustomize }) {
  useDocumentTitle(pageTitle("Rulebook"));
  useEffect(() => {
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
  }, []);

  return (
    <div className="page-frame">
      <main className="rulebook-page-shell">
        <LandingNav active="rulebook" onHome={onHome} onCustomize={onCustomize} />
        <RulebookReference catalog={catalog} />
      </main>
      <SiteFooter />
    </div>
  );
}

export default RulebookPage;
