function StableStatus({
  message = "",
  visible = Boolean(message),
  className = "",
  lines = 1,
  role = "status",
}) {
  return (
    <p
      className={`ui-stable-status${visible ? " is-visible" : ""} ${className}`.trim()}
      style={{ "--ui-status-lines": Math.max(1, lines) }}
      role={role}
      aria-live="polite"
      aria-atomic="true"
      title={visible ? message : undefined}
    >
      <span>{message || "\u00a0"}</span>
    </p>
  );
}

export default StableStatus;
