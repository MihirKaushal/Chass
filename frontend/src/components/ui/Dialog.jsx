import { useEffect, useId, useRef } from "react";

import IconCloseButton from "../IconCloseButton";

const FOCUSABLE_SELECTOR = [
  "button:not([disabled])",
  "a[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function Dialog({
  open,
  onClose,
  eyebrow,
  title,
  description,
  children,
  actions,
  className = "",
  initialFocusRef,
  closeLabel = "Close dialog",
  closeOnBackdrop = true,
  ariaLive,
}) {
  const panelRef = useRef(null);
  const onCloseRef = useRef(onClose);
  const generatedId = useId().replaceAll(":", "");
  const titleId = `dialog-title-${generatedId}`;
  const descriptionId = description ? `dialog-description-${generatedId}` : undefined;

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return undefined;

    const previouslyFocused = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const focusFrame = window.requestAnimationFrame(() => {
      const preferred = initialFocusRef?.current;
      const firstControl = panelRef.current?.querySelector(FOCUSABLE_SELECTOR);
      (preferred || firstControl || panelRef.current)?.focus();
    });

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current?.();
        return;
      }
      if (event.key !== "Tab") return;

      const controls = [...(panelRef.current?.querySelectorAll(FOCUSABLE_SELECTOR) || [])];
      if (!controls.length) {
        event.preventDefault();
        panelRef.current?.focus();
        return;
      }
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      window.cancelAnimationFrame(focusFrame);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus?.();
    };
  }, [initialFocusRef, open]);

  if (!open) return null;

  return (
    <div
      className="ui-dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (closeOnBackdrop && event.target === event.currentTarget) onClose?.();
      }}
    >
      <section
        ref={panelRef}
        className={`ui-dialog ${className}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        aria-live={ariaLive}
        tabIndex={-1}
      >
        {onClose ? (
          <IconCloseButton
            className="ui-dialog-close"
            label={closeLabel}
            onClick={onClose}
          />
        ) : null}
        <header className="ui-dialog-header">
          {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
          <h2 id={titleId}>{title}</h2>
          {description ? <p id={descriptionId}>{description}</p> : null}
        </header>
        {children ? <div className="ui-dialog-body">{children}</div> : null}
        {actions ? <footer className="ui-dialog-actions">{actions}</footer> : null}
      </section>
    </div>
  );
}

export default Dialog;
