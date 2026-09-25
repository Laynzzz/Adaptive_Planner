import { useQuery } from "@tanstack/react-query";
import Workspace from "./features/Workspace";

async function checkReadiness(): Promise<boolean> {
  const response = await fetch("/health/ready", {
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok || (await response.json()).status !== "ready") {
    throw new Error("Workspace is unavailable");
  }
  return true;
}

export default function App() {
  const readiness = useQuery({
    queryKey: ["readiness"],
    queryFn: checkReadiness,
    retry: false,
  });
  return (
    <div className="app-layout">
      <a className="skip-link" href="#main">
        Skip to workspace
      </a>
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="Adaptive Planner home">
          <span className="brand-symbol" aria-hidden="true">
            a
          </span>
          <span>
            Adaptive
            <br />
            <strong>Planner</strong>
          </span>
        </a>
        <nav aria-label="Workspace">
          <a href="#main" aria-current="page">
            My agenda
          </a>
        </nav>
        <p className="sidebar-note">
          A little structure.
          <br />
          Room to adapt.
        </p>
      </aside>
      <main id="main" className="main-content">
        <header className="workspace-header">
          <span>Personal workspace</span>
          <span className="connection" role="status">
            <span
              className={`status-dot ${readiness.isSuccess ? "ready" : ""}`}
              aria-hidden="true"
            />
            {readiness.isPending
              ? "Connecting…"
              : readiness.isSuccess
                ? "Workspace connected"
                : "Connection unavailable"}
          </span>
        </header>
        <section className="welcome" aria-labelledby="welcome-title">
          <h1 id="welcome-title">Make room for what matters.</h1>
          <p>
            Bring your tasks, deadlines, and available hours together. Review a
            plan before making it yours.
          </p>
        </section>
        {readiness.isError && (
          <section className="error-message" role="alert">
            <div>
              <strong>Workspace is unavailable</strong>
              <p>
                Your connection could not be established. Check that the local
                services are running, then try again.
              </p>
            </div>
            <button
              onClick={() => void readiness.refetch()}
              disabled={readiness.isFetching}
            >
              Try again
            </button>
          </section>
        )}
        <section className="agenda-surface" aria-labelledby="agenda-title">
          <header className="section-header">
            <h2 id="agenda-title">Your agenda</h2>
            <span>14-day planning window</span>
          </header>
          {readiness.isSuccess && <Workspace />}
        </section>
        <footer className="workspace-footer">
          Plans stay under your control. Changes require your review.
        </footer>
      </main>
    </div>
  );
}
