import { useState } from "react";
import { api } from "../api";

export default function AdminPanel() {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const restart = async (target: "backend" | "frontend") => {
    setBusy(true);
    setMessage(`Restarting ${target}...`);
    try {
      const fn = target === "backend" ? api.restartBackend : api.restartFrontend;
      const res = await fn();
      setMessage(res.status);
      // If we're restarting the frontend, the page will reload when Vite comes back
      if (target === "frontend") {
        setTimeout(() => {
          setMessage("Frontend is restarting — page will reload...");
          // Poll until the frontend is back
          const poll = setInterval(async () => {
            try {
              await fetch("/api/health");
              clearInterval(poll);
              window.location.reload();
            } catch {
              // still restarting
            }
          }, 1000);
        }, 1500);
      } else {
        // Backend restart — poll until it's back
        setTimeout(() => {
          setMessage("Backend is restarting...");
          const poll = setInterval(async () => {
            try {
              await api.adminStatus();
              clearInterval(poll);
              setMessage("Backend restarted successfully ✓");
              setBusy(false);
            } catch {
              // still restarting
            }
          }, 1000);
        }, 1500);
      }
    } catch (e) {
      setMessage(`Failed: ${e instanceof Error ? e.message : String(e)}`);
      setBusy(false);
    }
  };

  return (
    <div className="admin-panel">
      <div className="admin-buttons">
        <button
          className="admin-btn backend"
          onClick={() => restart("backend")}
          disabled={busy}
          title="Restart FastAPI backend (run_all.sh must be running)"
        >
          ⟳ Restart Backend
        </button>
        <button
          className="admin-btn frontend"
          onClick={() => restart("frontend")}
          disabled={busy}
          title="Restart Vite dev server (run_all.sh must be running)"
        >
          ⟳ Restart Frontend
        </button>
      </div>
      {message && <span className="admin-message">{message}</span>}
    </div>
  );
}
