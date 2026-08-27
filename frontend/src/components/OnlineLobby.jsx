import { useState } from "react";

import Button from "./ui/Button";
import FormField from "./ui/FormField";
import StableStatus from "./ui/StableStatus";

function OnlineLobby({
  game,
  session,
  onReplaceInvite,
}) {
  const [copyState, setCopyState] = useState("");
  const isHost = session?.role === "host";
  const inviteUrl = session?.inviteUrl;
  const inviteCode = session?.inviteCode || session?.inviteToken;

  if (game.ready || !isHost) {
    return null;
  }

  const copyInvite = async (value, successMessage) => {
    if (!value) {
      return;
    }

    try {
      await navigator.clipboard.writeText(value);
      setCopyState(successMessage);
    } catch {
      setCopyState("Select and copy from the field above");
    }
  };

  return (
    <section className="online-invite-panel" aria-label="Online game invitation">
      <div className="online-invite-heading">
        <strong>Invite Black</strong>
        <span>Share the private link or code.</span>
      </div>
      <div className="invite-controls">
        {inviteUrl ? (
          <>
            <FormField label="Private Invite Link">
              <input type="text" value={inviteUrl} readOnly onFocus={(event) => event.target.select()} />
            </FormField>
            <Button onClick={() => copyInvite(inviteUrl, "Invite link copied")}>
              Copy Invite Link
            </Button>
            <FormField className="invite-code-field" label="Invite Code">
              <input type="text" value={inviteCode || ""} readOnly onFocus={(event) => event.target.select()} />
            </FormField>
            <Button onClick={() => copyInvite(inviteCode, "Invite code copied")}>
              Copy Invite Code
            </Button>
          </>
        ) : (
          <Button onClick={onReplaceInvite}>
            Create New Invite
          </Button>
        )}
        <StableStatus
          className="invite-copy-status"
          visible={Boolean(copyState)}
          message={copyState}
          lines={2}
        />
      </div>
    </section>
  );
}

export default OnlineLobby;
