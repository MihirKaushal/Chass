import { useEffect, useState } from "react";

import Button from "./ui/Button";
import FormField from "./ui/FormField";
import StableStatus from "./ui/StableStatus";

function OnlineLobby({
  session,
  inviteState,
  returnUrl,
  onReplaceInvite,
}) {
  const [copyState, setCopyState] = useState("");
  const reconnect = Boolean(inviteState?.reconnect);
  const inviteUrl = reconnect ? returnUrl : session?.inviteUrl;
  const inviteCode = session?.inviteCode || session?.inviteToken;
  const targetLabel = inviteState?.targetColor === "white" ? "White" : "Black";

  useEffect(() => setCopyState(""), [inviteCode, inviteState?.targetColor, reconnect]);

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
      className={`online-invite-panel${reconnect ? " is-reconnect" : ""}`}
      aria-label={`${reconnect ? "Reconnect" : "Invite"} ${targetLabel} to the online game`}
    >
      <div className="online-invite-heading">
        <strong>{reconnect ? `Reconnect ${targetLabel}` : `Invite ${targetLabel}`}</strong>
        <span>
          {reconnect
            ? `${targetLabel} is offline. Their seat is reserved. Reopen this link in the browser they used to join.`
            : "Share the private link or code."}
        </span>
      </div>
      <div className="invite-controls">
        {reconnect ? (
          <>
            <FormField label="Return to game">
              <input type="text" value={inviteUrl || ""} readOnly onFocus={(event) => event.target.select()} />
            </FormField>
            <Button onClick={() => copyInvite(inviteUrl, "Game link copied")}>
              Copy game link
            </Button>
          </>
        ) : inviteUrl ? (
          <>
            <FormField label="Private invite link">
              <input type="text" value={inviteUrl} readOnly onFocus={(event) => event.target.select()} />
            </FormField>
            <Button onClick={() => copyInvite(inviteUrl, "Invite link copied")}>
              Copy invite link
            </Button>
            <FormField className="invite-code-field" label="Invite code">
              <input type="text" value={inviteCode || ""} readOnly onFocus={(event) => event.target.select()} />
            </FormField>
            <Button onClick={() => copyInvite(inviteCode, "Invite code copied")}>
              Copy invite code
            </Button>
          </>
        ) : (
          <Button onClick={onReplaceInvite}>Create new invite</Button>
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
