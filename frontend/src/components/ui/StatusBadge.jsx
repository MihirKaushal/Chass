function StatusBadge({
  children,
  tone = "neutral",
  className = "",
  icon,
  busy = false,
  as: Tag = "span",
}) {
  return (
    <Tag
      className={`ui-status-badge ui-status-badge--${tone} ${className}`.trim()}
      aria-busy={busy || undefined}
    >
      {busy ? (
        <i className="ui-status-spinner" aria-hidden="true" />
      ) : icon ? (
        <i aria-hidden="true">{icon}</i>
      ) : null}
      <span>{children}</span>
    </Tag>
  );
}

export default StatusBadge;
