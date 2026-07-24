import { useState } from "react";


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

  const copyInvite = async () => {
    if (!inviteUrl) {
      return;
    }

    try {
      await navigator.clipboard.writeText(inviteUrl);
      setCopyState("Invite copied");
    } catch {
      setCopyState("Select and copy the link below");
    }
  };

  return (
    <section className={`online-room ${game.ready ? "online-room--ready" : ""}`}>
      <div>
        <span className="eyebrow">Online room</span>
        <h2>{game.ready ? "Both players are in" : "Waiting for Black"}</h2>
        <p>
          You are playing as <strong>{session?.color || "spectator"}</strong>. The server is{" "}
          <strong>{connectionStatus}</strong>.
        </p>
      </div>

      <div className="seat-status" aria-label="Player connection status">
        <span className={presence.white ? "seat connected" : "seat"}>
          White {presence.white ? "connected" : "offline"}
        </span>
        <span className={presence.black ? "seat connected" : "seat"}>
          Black {game.players.black === "open" ? "open" : presence.black ? "connected" : "offline"}
        </span>
      </div>

      {!game.ready && isHost ? (
        <div className="invite-controls">
          {inviteUrl ? (
            <>
              <label>
                Share this private invite
                <input type="text" value={inviteUrl} readOnly onFocus={(event) => event.target.select()} />
              </label>
              <button type="button" onClick={copyInvite}>
                Copy Invite Link
              </button>
            </>
          ) : (
            <button type="button" onClick={onReplaceInvite}>
              Create New Invite
            </button>
          )}
          {copyState ? <small aria-live="polite">{copyState}</small> : null}
        </div>
      ) : null}
    </section>
  );
}

export default OnlineLobby;
