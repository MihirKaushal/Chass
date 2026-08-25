function StatusBadge({ children, tone = "neutral", className = "", icon }) {
  return (
    <span className={`ui-status-badge ui-status-badge--${tone} ${className}`.trim()}>
      {icon ? <i aria-hidden="true">{icon}</i> : null}
      <span>{children}</span>
    </span>
  );
}

export default StatusBadge;
