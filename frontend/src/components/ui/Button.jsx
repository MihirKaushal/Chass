import { forwardRef } from "react";

const Button = forwardRef(function Button(
  {
    children,
    className = "",
    variant = "primary",
    size = "medium",
    loading = false,
    loadingLabel = "",
    disabled = false,
    type = "button",
    ...props
  },
  ref
) {
  const resolvedLoadingLabel = loadingLabel || "Working...";
  const variantClass = variant === "secondary" ? " secondary" : "";
  const loadingClass = loading ? " is-loading" : "";

  return (
    <button
      {...props}
      ref={ref}
      type={type}
      className={`ui-button ui-button--${variant} ui-button--${size}${variantClass}${loadingClass} ${className}`.trim()}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      <span className="ui-button-content" aria-hidden={loading || undefined}>
        {children}
      </span>
      {loading || loadingLabel ? (
        <span className="ui-button-progress" aria-hidden={!loading}>
          <i aria-hidden="true" />
          <span>{resolvedLoadingLabel}</span>
        </span>
      ) : null}
    </button>
  );
});

export default Button;
