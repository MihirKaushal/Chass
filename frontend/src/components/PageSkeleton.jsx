function SkeletonLine({ size = "medium" }) {
  return <span className={`skeleton-block skeleton-line ${size}`} aria-hidden="true" />;
}

function SkeletonPanel({ rows = 3, className = "" }) {
  return (
    <div className={`skeleton-panel ${className}`.trim()} aria-hidden="true">
      <SkeletonLine size="short" />
      {Array.from({ length: rows }).map((_, index) => (
        <SkeletonLine key={index} size={index === rows - 1 ? "medium" : "long"} />
      ))}
    </div>
  );
}

function SkeletonNavigation() {
  return (
    <div className="skeleton-navigation" aria-hidden="true">
      <div className="skeleton-brand"><SkeletonLine size="short" /><SkeletonLine size="medium" /></div>
      <div className="skeleton-tabs"><span className="skeleton-block" /><span className="skeleton-block" /></div>
      <div className="skeleton-nav-status"><span className="skeleton-block" /><span className="skeleton-block" /></div>
    </div>
  );
}

function PlaySkeleton() {
  return (
    <div className="skeleton-play-body" aria-hidden="true">
      <div className="skeleton-status-rail"><span className="skeleton-block" /><span className="skeleton-block" /></div>
      <div className="skeleton-play-grid">
        <SkeletonPanel rows={5} className="skeleton-play-side" />
        <div className="skeleton-board-panel">
          <div className="skeleton-block skeleton-board" />
          <div className="skeleton-block skeleton-action-rail" />
        </div>
        <SkeletonPanel rows={6} className="skeleton-play-side" />
      </div>
    </div>
  );
}

function CustomizeSkeleton() {
  return (
    <section className="skeleton-customize-body" aria-hidden="true">
      <div className="skeleton-customize-hero">
        <div><SkeletonLine size="short" /><SkeletonLine size="long" /><SkeletonLine size="medium" /></div>
        <span className="skeleton-block skeleton-hero-button" />
      </div>
      <div className="skeleton-customize-grid">
        <div className="skeleton-preview-column">
          <div className="skeleton-panel"><div className="skeleton-block skeleton-preview-board" /></div>
          <SkeletonPanel rows={2} />
        </div>
        <div className="skeleton-control-column">
          <SkeletonPanel rows={3} />
          <SkeletonPanel rows={2} />
          <SkeletonPanel rows={4} />
          <SkeletonPanel rows={3} />
          <SkeletonPanel rows={2} />
        </div>
      </div>
      <div className="skeleton-launch-bar"><SkeletonLine size="medium" /><span className="skeleton-block" /></div>
    </section>
  );
}

function PageSkeleton({ variant = "play", embedded = false }) {
  return (
    <div
      className={`page-skeleton page-skeleton-${variant}${embedded ? " is-embedded" : ""}`}
      role="status"
      aria-busy="true"
      aria-live="polite"
    >
      <span className="visually-hidden">Loading Chass</span>
      {!embedded ? <SkeletonNavigation /> : null}
      {variant === "customize" ? <CustomizeSkeleton /> : <PlaySkeleton />}
      {!embedded ? <span className="skeleton-block skeleton-footer-line" aria-hidden="true" /> : null}
    </div>
  );
}

export default PageSkeleton;
