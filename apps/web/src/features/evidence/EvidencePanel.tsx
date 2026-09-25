import r1 from "../../../../../docs/evidence/r1-release.md?raw";
import adaptation from "../../../../../docs/evidence/task-8-adaptation.md?raw";
import extraction from "../../../../../docs/evidence/ai-evaluation.md?raw";
import calendar from "../../../../../docs/evidence/task-11-12-calendar.md?raw";
import interfaceReport from "../../../../../docs/evidence/r2-ui.md?raw";
import aiRaw from "../../../../../docs/evidence/raw/ai-mock-test.json?raw";
import sql from "../../../../../docs/evidence/sql-performance.md?raw";
import ml from "../../../../../docs/evidence/ml-experiment.md?raw";
import mlRaw from "../../../../../docs/evidence/raw/ml-test-summary.json?raw";
import { useState } from "react";

const reports = [
  { name: "R1 release", text: r1, file: "r1-release.md" },
  { name: "Adaptive planning", text: adaptation, file: "task-8-adaptation.md" },
  { name: "AI evaluation", text: extraction, file: "ai-evaluation.md" },
  { name: "Calendar recovery", text: calendar, file: "task-11-12-calendar.md" },
  { name: "Browser workflows", text: interfaceReport, file: "r2-ui.md" },
  { name: "Raw mock test results", text: aiRaw, file: "ai-mock-test.json" },
  { name: "SQL measurements", text: sql, file: "sql-performance.md" },
  { name: "Routing experiment", text: ml, file: "ml-experiment.md" },
  { name: "Routing test summary", text: mlRaw, file: "ml-test-summary.json" },
];

function Report({ report }: { report: (typeof reports)[number] }) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="evidence-report"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>{report.name}</summary>
      {open && (
        <>
          <a
            className="button-link"
            download={report.file}
            href={`data:text/plain;charset=utf-8,${encodeURIComponent(report.text)}`}
          >
            Download {report.name} report
          </a>
          <pre>{report.text}</pre>
        </>
      )}
    </details>
  );
}

export default function EvidencePanel() {
  return (
    <section
      className="agenda-surface evidence-panel"
      aria-labelledby="evidence-title"
    >
      <header className="section-header">
        <h2 id="evidence-title">What has been verified</h2>
        <span>Local evidence · September 25, 2026</span>
      </header>
      <div className="plan-body">
        <p>
          This is an agent-assisted project tested with synthetic tasks. These
          results describe specific local checks, not production reliability or
          human time savings.
        </p>
        <div className="evidence-scroll">
          <table>
            <caption>Capabilities and verification scope</caption>
            <thead>
              <tr>
                <th>Capability</th>
                <th>Observed evidence</th>
                <th>Limits</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th>Planning and isolation</th>
                <td>
                  Independent validation, tiny-instance comparisons, PostgreSQL
                  concurrency checks and two-user browser journeys.
                </td>
                <td>Scheduling uses a 15-minute grid and a 14-day horizon.</td>
              </tr>
              <tr>
                <th>Reviewed changes</th>
                <td>
                  Progress, locks, what-if previews, task and weekday-rule
                  acceptance tested through the browser.
                </td>
                <td>
                  Input changes and plan activation remain separate actions.
                </td>
              </tr>
              <tr>
                <th>Local extraction</th>
                <td>
                  87 of 90 critical fields matched in 30 held-out synthetic
                  examples.
                </td>
                <td>
                  Fixed demo parser. Independent human reference review and live
                  AI evaluation pending.
                </td>
              </tr>
              <tr>
                <th>Calendar recovery</th>
                <td>
                  ICS export and durable simulator tests cover uncertain writes,
                  manual edits and retry.
                </td>
                <td>Live Google has not been verified.</td>
              </tr>
              <tr>
                <th>SQL performance</th>
                <td>Large synthetic task-page reads: p95 46.93 → 5.44 ms.</td>
                <td>
                  Writes cost more; end-to-end plan readiness did not improve.
                </td>
              </tr>
              <tr>
                <th>Learned routing</th>
                <td>
                  1,000 measured scenario groups. Held-out routing failed
                  completion, quality and latency gates.
                </td>
                <td>
                  Not promoted. Fixed routing remains active. Old
                  process-timeout measurements also have a documented
                  supervision limitation.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="inline-error">
          Live Google, paid AI evaluation and AWS deployment have not been
          executed.
        </p>
        <h3>Reports and raw results</h3>
        <p>
          These reports are bundled with this build and remain readable when the
          planning service is unavailable. Downloaded reports use
          repository-relative evidence links.
        </p>
        {reports.map((report) => (
          <Report key={report.file} report={report} />
        ))}
      </div>
    </section>
  );
}
