# Five-minute product demonstration

This is an **agent-operated synthetic scripted walkthrough**, not a human usability study. The browser uses real local OIDC login, PostgreSQL, API and separate solver/extraction/calendar workers. Text extraction and calendar publication use local simulators. No live AI, Google Calendar or cloud deployment is demonstrated.

Run `node scripts/demo-browser.mjs` from the repository root after starting the documented local PostgreSQL and Keycloak services. Ports 8000 and 5173 must be free. The script creates a uniquely named `planner_demo_*` database, migrates it, starts its own processes and records Chromium at 1440×1080. It refuses a nonempty synthetic workspace. `--rehearsal` skips intentional reading pauses and produces separately labeled evidence. Each run retains a manifest, screenshots, ICS, service logs and video under ignored `.runtime/demo/`. Only processes launched by the script are stopped. The isolated local database is retained for inspection; it incurs no provider billing.

| Approximate time | Visible action | Assertion |
| --- | --- | --- |
| 0:00–1:10 | Sign in; enter two 60-minute tasks and a three-hour window; review and activate | Initially empty workspace; valid blocks; explicit activation |
| 1:10–1:40 | Record missed work: zero observed, 60 still remaining | Work log appears; active plan remains selected |
| 1:40–2:20 | Lock one block, generate and activate a replan | Locked start/end remain identical |
| 2:20–3:00 | Preview a 300-minute estimate inside the existing window | Infeasibility visible; actual task estimate and active plan unchanged |
| 3:00–3:50 | Extract a task using the local text simulator; review unknown/inferred fields | No task added before review; confirmation enables acceptance |
| 3:50–4:47 | Export ICS; explicitly connect dedicated simulator; show one injected API 503 and retry | Portable file; visible error; publication converges; disconnect keeps events |
| 4:47–5:00 | Show Evidence & limits | Local evidence and remaining gates remain explicit |

The overlay is a recording aid injected into the browser DOM. It does not change application behavior. The calendar failure is explicitly labeled **test-only API-response injection**. This recording does not establish ambiguous remote-write recovery; the dedicated calendar fault tests establish that local simulator behavior separately.

## Deeper walkthrough outline

The separate [technical walkthrough](technical-walkthrough.md) is recorded and hashed. It explains greedy/CP-SAT validation, revision and lease races, process-tree supervision, measured SQL tradeoffs and the frozen negative ML result. Its five-minute source-screen narrative is labeled agent-produced and observational where appropriate; it makes no personal-practice claim.
