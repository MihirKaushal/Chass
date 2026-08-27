import { useEffect, useState } from "react";

import Button from "./ui/Button";
import FormField from "./ui/FormField";
import StableStatus from "./ui/StableStatus";

function OnlineLobby({
  session,
  inviteState,
  reconnectInvite,
  reconnectInviteLoading,
  onRetryReconnectInvite,
  onReplaceInvite,
}) {
  const [copyState, setCopyState] = useState("");
  const activeInvite = inviteState?.reconnect ? reconnectInvite : session;
  const inviteUrl = activeInvite?.inviteUrl;
  const inviteCode = activeInvite?.inviteCode || activeInvite?.inviteToken;
  const targetLabel = inviteState?.targetColor === "white" ? "White" : "Black";

  useEffect(() => setCopyState(""), [inviteCode, inviteState?.targetColor]);

  if (!inviteState) return null;

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
    <section
      className={`online-invite-panel${inviteState.reconnect ? " is-reconnect" : ""}`}
      aria-label={`Invite ${targetLabel} to the online game`}
    >
      <div className="online-invite-heading">
        <strong>Invite {targetLabel}</strong>
        <span>
          {inviteState.reconnect
            ? `${targetLabel} is offline. Share a fresh one-time link or code to continue.`
            : "Share the private link or code."}
        </span>
      </div>
      <div className="invite-controls">
        {reconnectInviteLoading && !inviteUrl ? (
          <StableStatus
            className="invite-generation-status"
            visible
            message={`Creating ${targetLabel}'s reconnect invite...`}
          />
        ) : inviteUrl ? (
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
          <Button
            onClick={inviteState.reconnect ? onRetryReconnectInvite : onReplaceInvite}
          >
            {inviteState.reconnect ? "Try Again" : "Create New Invite"}
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
