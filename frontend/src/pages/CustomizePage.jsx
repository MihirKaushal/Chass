import { useState } from "react";

import LandingNav from "../components/LandingNav";
import CustomizationPanel from "../components/CustomizationPanel";
import SiteFooter from "../components/SiteFooter";
import Button from "../components/ui/Button";
import Dialog from "../components/ui/Dialog";
import { shouldConfirmDiscardingCustomization } from "../leaveGameGuard";
import { navigate, useNavigationBlocker } from "../routing";

function LeaveCustomizeConfirmation({ open, onCancel, onConfirm }) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      closeLabel="Close leave Customize confirmation"
      eyebrow="Unsaved Configuration"
      title="Leave Game Customizer?"
      description="Your custom game settings will be lost if you leave this page before starting a game."
      actions={(
        <>
          <Button variant="secondary" onClick={onCancel}>
            Keep Editing
          </Button>
          <Button variant="danger" onClick={onConfirm}>Leave Game Customizer</Button>
        </>
      )}
    />
  );
}

function CustomizePage({ onCreate, onHome, initialPreset = "" }) {
  const [configurationModified, setConfigurationModified] = useState(false);
  const [confirmingLeave, setConfirmingLeave] = useState(false);
  const [pendingLeaveDestination, setPendingLeaveDestination] = useState("/");

  useNavigationBlocker(
    (destination) => {
      if (!shouldConfirmDiscardingCustomization(configurationModified)) return true;
      setPendingLeaveDestination(destination);
      setConfirmingLeave(true);
      return false;
    },
    shouldConfirmDiscardingCustomization(configurationModified)
  );

  const requestHome = () => {
    if (shouldConfirmDiscardingCustomization(configurationModified)) {
      setPendingLeaveDestination("/");
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
        onConfirm={() => {
          setConfirmingLeave(false);
          navigate(pendingLeaveDestination, { bypassBlocker: true });
        }}
      />
    </div>
  );
}

export default CustomizePage;
