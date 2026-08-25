function DisclosureIndicator({ className = "" }) {
  return (
    <span
      className={`ui-disclosure-indicator disclosure-arrow ${className}`.trim()}
      aria-hidden="true"
    />
  );
}

function Disclosure({
  id,
  className = "",
  summaryClassName = "",
  bodyClassName = "",
  open,
  onToggle,
  summary,
  children,
}) {
  return (
    <details
      id={id}
      className={`ui-disclosure ${className}`.trim()}
      open={open}
      onToggle={onToggle}
    >
      <summary className={summaryClassName}>
        {summary}
        <DisclosureIndicator />
      </summary>
      <div className={`ui-disclosure-body ${bodyClassName}`.trim()}>{children}</div>
    </details>
  );
}

export { DisclosureIndicator };
export default Disclosure;
