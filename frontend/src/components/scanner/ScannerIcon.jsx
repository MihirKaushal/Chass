function ScannerIcon({ name, className = "" }) {
  const marks = {
    upload: (
      <>
        <path d="M12 16V3m-5 5 5-5 5 5" />
        <path d="M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5" />
      </>
    ),
    camera: (
      <>
        <path d="m8 5 1-2h6l1 2h4a1 1 0 0 1 1 1v14H3V6a1 1 0 0 1 1-1Z" />
        <circle cx="12" cy="12" r="4" />
      </>
    ),
    light: (
      <>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" />
      </>
    ),
    top: (
      <>
        <rect x="4" y="7" width="16" height="14" rx="2" />
        <path d="M9 12h6m-3-9v9m-3-3 3 3 3-3M4 16h16m-11 0v5m6-5v5" />
      </>
    ),
    align: (
      <>
        <path d="M3 8V3h5m8 0h5v5M3 16v5h5m8 0h5v-5" />
        <circle cx="12" cy="11" r="3" />
        <path d="M8 17h8" />
      </>
    ),
    rotate: (
      <>
        <path d="M4 10a8 8 0 1 1 1 8M4 4v6h6" />
      </>
    ),
    undo: (
      <>
        <path d="m8 3-5 5 5 5M3 8h10a7 7 0 0 1 0 14" />
      </>
    ),
    eraser: (
      <>
        <path d="m4 13 9-9a2 2 0 0 1 3 0l4 4a2 2 0 0 1 0 3l-9 9H8l-4-4a2 2 0 0 1 0-3Z" />
        <path d="m9 8 7 7M11 20h10" />
      </>
    ),
    info: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v6m0-10v.1" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    monitor: (
      <>
        <rect x="3" y="4" width="18" height="13" rx="2" />
        <path d="M8 21h8m-4-4v4" />
      </>
    ),
    globe: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z" />
      </>
    ),
    bot: (
      <>
        <rect x="4" y="7" width="16" height="14" rx="3" />
        <path d="M12 3v4M1 12v5m22-5v5M8 16h8M8 11v1m8-1v1" />
        <circle cx="12" cy="3" r="1" />
      </>
    ),
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  };

  return (
    <svg
      className={`scanner-icon ${className}`.trim()}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      {marks[name] || marks.info}
    </svg>
  );
}

export default ScannerIcon;
