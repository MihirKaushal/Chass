import { useEffect, useRef, useState } from "react";


function JoinPage({ inviteToken, onJoin, onHome }) {
  const startedRef = useRef(false);
  const [status, setStatus] = useState("Joining your game...");
  const [error, setError] = useState("");

  const join = async () => {
    setError("");
    setStatus("Joining your game...");
    try {
      await onJoin(inviteToken);
    } catch (requestError) {
      setStatus("");
      setError(requestError.message);
    }
  };

  useEffect(() => {
    if (startedRef.current) {
      return;
    }
    startedRef.current = true;
    join();
  }, [inviteToken]);

  return (
    <main className="landing-shell">
      <section className="join-card">
        <span className="eyebrow">Private game invitation</span>
        <h1>{error ? "Unable to join" : "Taking the Black seat"}</h1>
        {status ? <p className="join-status">{status}</p> : null}
        {error ? <p className="landing-error">{error}</p> : null}
        {error ? (
          <div className="button-row">
            <button type="button" onClick={join}>
              Try Again
            </button>
            <button type="button" className="secondary" onClick={onHome}>
              Back Home
            </button>
          </div>
        ) : null}
      </section>
    </main>
  );
}

export default JoinPage;
