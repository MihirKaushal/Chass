import { forwardRef } from "react";

const IconCloseButton = forwardRef(function IconCloseButton(
  { className = "", label, onClick },
  ref
) {
  return (
    <button
      ref={ref}
      type="button"
      className={`icon-close-button ${className}`.trim()}
      aria-label={label}
      onClick={onClick}
    >
      <span aria-hidden="true">×</span>
    </button>
  );
});

export default IconCloseButton;
