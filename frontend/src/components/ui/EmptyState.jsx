function EmptyState({ children, className = "", role }) {
  return (
    <p className={`ui-empty-state ${className}`.trim()} role={role}>
      {children}
    </p>
  );
}

export default EmptyState;
