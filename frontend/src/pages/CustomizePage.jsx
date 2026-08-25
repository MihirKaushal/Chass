import { useEffect, useRef, useState } from "react";

import LandingNav from "../components/LandingNav";
import CustomizationPanel from "../components/CustomizationPanel";
import SiteFooter from "../components/SiteFooter";
import { shouldConfirmDiscardingCustomization } from "../leaveGameGuard";

function LeaveCustomizeConfirmation({ open, onCancel, onConfirm }) {
  const cancelRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    cancelRef.current?.focus();
    const closeOnEscape = (event) => {
      if (event.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onCancel, open]);

  if (!open) return null;
  return (
    <div
      className="starting-system-dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <section
        className="starting-system-dialog leave-customize-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="leave-customize-dialog-title"
        aria-describedby="leave-customize-dialog-description"
      >
        <span className="eyebrow">Unsaved Configuration</span>
        <h2 id="leave-customize-dialog-title">Leave Customize?</h2>
        <p id="leave-customize-dialog-description">
          Your custom game settings will be lost if you return home before starting a game.
        </p>
        <div className="starting-system-dialog-actions">
          <button type="button" className="secondary" ref={cancelRef} onClick={onCancel}>
            Keep Editing
          </button>
          <button type="button" onClick={onConfirm}>Leave And Go Home</button>
        </div>
      </section>
    </div>
  );
}

function CustomizePage({ onCreate, onHome, initialPreset = "" }) {
  const [configurationModified, setConfigurationModified] = useState(false);
  const [confirmingLeave, setConfirmingLeave] = useState(false);

  const requestHome = () => {
    if (shouldConfirmDiscardingCustomization(configurationModified)) {
      setConfirmingLeave(true);
      return;
    }
    onHome();
  };

  return (
    <div className="page-frame">
      <main className="customize-page-shell">
        <LandingNav active="customize" onHome={requestHome} onCustomize={() => {}} />
        <CustomizationPanel
          onCreate={onCreate}
          initialPreset={initialPreset}
          onModificationChange={setConfigurationModified}
        />
      </main>
      <SiteFooter />
      <LeaveCustomizeConfirmation
        open={confirmingLeave}
        onCancel={() => setConfirmingLeave(false)}
        onConfirm={onHome}
      />
    </div>
  );
}

export default CustomizePage;
