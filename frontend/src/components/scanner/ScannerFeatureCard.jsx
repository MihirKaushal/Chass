import AppLink from "../AppLink";
import ScannerIcon from "./ScannerIcon";

export default function ScannerFeatureCard() {
  return (
    <article className="scanner-feature-card">
      <div className="scanner-feature-illustration" aria-hidden="true">
        <svg viewBox="0 0 180 100" focusable="false">
          <rect x="4" y="10" width="68" height="80" rx="8" className="scanner-feature-photo" />
          <path d="M13 31V20h11m28 0h11v11M13 69v11h11m28 0h11V69" />
          <circle cx="38" cy="39" r="8" />
          <path d="M32 47l-6 18h24l-6-18M24 70h28M80 50h19m-6-6 6 6-6 6" />
          {Array.from({ length: 16 }, (_, i) => <rect key={i} x={108 + i % 4 * 16} y={18 + Math.floor(i / 4) * 16}
            width="16" height="16" className={(i % 4 + Math.floor(i / 4)) % 2 ? "scanner-feature-dark" : "scanner-feature-light"} />)}
          <circle cx="132" cy="40" r="5" className="scanner-feature-piece" />
          <path d="m128 45-4 12h16l-4-12M123 61h18" />
        </svg>
      </div>
      <div>
        <h2>Continue Your Physical Game</h2>
        <p>Scan your chessboard, review the pieces, and continue on Chass.</p>
      </div>
      <AppLink href="/scanner" className="ui-button ui-button--primary">
        <span className="ui-button-content"><ScannerIcon name="camera" /> Scan a Board</span>
      </AppLink>
    </article>
  );
}
