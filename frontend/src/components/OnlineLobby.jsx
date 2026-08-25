import { useState } from "react";

import Button from "./ui/Button";
import FormField from "./ui/FormField";
import StableStatus from "./ui/StableStatus";
import StatusBadge from "./ui/StatusBadge";

function OnlineLobby({
  game,
  session,
  presence,
  connectionStatus,
  onReplaceInvite,
}) {
  const [copyState, setCopyState] = useState("");
  const isHost = session?.role === "host";
  const inviteUrl = session?.inviteUrl;
  const inviteCode = session?.inviteCode || session?.inviteToken;

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
    <section className={`online-room ${game.ready ? "online-room--ready" : ""}`}>
      <div>
        <span className="eyebrow">Online Room</span>
        <h2>{game.ready ? "Both Players Are In" : "Waiting For Black"}</h2>
        <p>
          You are playing as <strong>{session?.color || "spectator"}</strong>. The server is{" "}
          <strong>{connectionStatus}</strong>.
        </p>
      </div>

      <div className="seat-status" aria-label="Player connection status">
        <StatusBadge tone={presence.white ? "success" : "neutral"} className={presence.white ? "seat connected" : "seat"}>
          White {presence.white ? "Connected" : "Offline"}
        </StatusBadge>
        <StatusBadge tone={presence.black ? "success" : "neutral"} className={presence.black ? "seat connected" : "seat"}>
          Black {game.players.black === "open" ? "Open" : presence.black ? "Connected" : "Offline"}
        </StatusBadge>
      </div>

      {!game.ready && isHost ? (
        <div className="invite-controls">
          {inviteUrl ? (
            <>
              <FormField label="Share This Private Link">
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
      ) : null}
    </section>
  );
}

export default OnlineLobby;
