function NewTabIcon({ className = "" }) {
  return (
    <svg
      className={`new-tab-icon ${className}`.trim()}
      viewBox="0 0 20 20"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M8 4H5.25A2.25 2.25 0 0 0 3 6.25v8.5A2.25 2.25 0 0 0 5.25 17h8.5A2.25 2.25 0 0 0 16 14.75V12" />
      <path d="M11 3h6v6M17 3l-8 8" />
    </svg>
  );
}

export default NewTabIcon;
