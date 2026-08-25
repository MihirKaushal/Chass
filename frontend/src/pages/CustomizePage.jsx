import { useState } from "react";

import LandingNav from "../components/LandingNav";
import CustomizationPanel from "../components/CustomizationPanel";
import SiteFooter from "../components/SiteFooter";
import Button from "../components/ui/Button";
import Dialog from "../components/ui/Dialog";
import { shouldConfirmDiscardingCustomization } from "../leaveGameGuard";

function LeaveCustomizeConfirmation({ open, onCancel, onConfirm }) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      closeLabel="Close leave Customize confirmation"
      eyebrow="Unsaved Configuration"
      title="Leave Customize?"
      description="Your custom game settings will be lost if you return home before starting a game."
      actions={(
        <>
          <Button variant="secondary" onClick={onCancel}>
            Keep Editing
          </Button>
          <Button variant="danger" onClick={onConfirm}>Leave And Go Home</Button>
        </>
      )}
    />
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
