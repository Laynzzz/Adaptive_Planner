import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { mutate, request, type Identity } from "../../api/client";
import type { components } from "../../api/generated";
import TimeExplanation from "./TimeExplanation";
import { conflictSummary } from "./conflicts";
type Proposal = components["schemas"]["ProposalView"];
type Job = components["schemas"]["JobView"];
const statusLabels: Record<string, string> = {
  OPTIMAL: "Optimal within the scheduling model",
  FEASIBLE: "Valid schedule found",
  INFEASIBLE: "These constraints cannot all be met",
  UNKNOWN: "No conclusion within the search budget",
  MODEL_INVALID: "Inputs or scheduling model need correction",
};
const runningStates = ["QUEUED", "RUNNING", "RETRY_WAIT"];

export default function PlanPanel({
  identity,
  onChanged,
  taskNames = {},
}: {
  identity: Identity;
  onChanged: () => void;
  taskNames?: Record<string, string>;
}) {
  const cache = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const command = useRef({ revision: -1, key: "" });
  const activation = useRef({ proposal: "", revision: -1, key: "" });
  const proposals = useQuery({
    queryKey: ["proposals", identity.id],
    queryFn: () => request<{ items: Proposal[] }>("/proposals"),
  });
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => request<Job>(`/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (query) =>
      runningStates.includes(query.state.data?.state ?? "QUEUED")
        ? 1000
        : false,
  });
  useEffect(() => {
    if (job.data && !runningStates.includes(job.data.state)) {
      void cache.invalidateQueries({ queryKey: ["proposals"] });
    }
  }, [job.data?.state, cache]);
  const latest = proposals.data?.items?.[0];
  const diff = useQuery({
    queryKey: ["plan-diff", latest?.id],
    queryFn: () =>
      request<components["schemas"]["PlanDiff"]>(
        `/proposals/${latest!.id}/diff`,
      ),
    enabled: !!latest?.id,
  });
  const running =
    !!jobId && (!job.data || runningStates.includes(job.data.state));
  const failedCandidate =
    job.data?.state === "FAILED" ? job.data.candidate : null;
  const candidate = failedCandidate ?? latest?.candidate;
  const violations = candidate?.constraint_report ?? [];
  const blocks = candidate?.blocks ?? [];
  const valid =
    candidate &&
    ["FEASIBLE", "OPTIMAL"].includes(candidate.status) &&
    violations.length === 0 &&
    !failedCandidate;
  const current = latest?.planning_revision === identity.revision;
  const formatTime = (time: string) =>
    new Intl.DateTimeFormat("en", {
      timeZone: identity.timezone,
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(time));
  return (
    <section className="plan-panel" aria-labelledby="plan-title">
      <div className="section-header">
        <div>
          <h2 id="plan-title">Plan proposal</h2>
          <p className="field-help">Review the result before activating it.</p>
        </div>
        <button
          disabled={busy || running}
          onClick={async () => {
            if (command.current.revision !== identity.revision)
              command.current = {
                revision: identity.revision,
                key: crypto.randomUUID(),
              };
            setBusy(true);
            setError("");
            setNotice("");
            try {
              const result = await mutate<{ job_id: string }>(
                "/replans",
                "POST",
                { expected_revision: identity.revision },
                identity.csrf_token,
                command.current.key,
              );
              setJobId(result.job_id);
              command.current = { revision: -1, key: "" };
            } catch (failure) {
              setError(
                failure instanceof Error
                  ? failure.message
                  : "Plan could not be requested.",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          {running ? "Planning…" : "Generate plan"}
        </button>
      </div>
      <div className="plan-body">
        {running && (
          <p role="status">
            {job.data?.state === "RUNNING"
              ? "Finding a schedule…"
              : "Waiting for a scheduling worker…"}
          </p>
        )}
        {job.isError && (
          <p role="alert">
            The job status could not be loaded.{" "}
            <button className="secondary" onClick={() => void job.refetch()}>
              Check status
            </button>
          </p>
        )}
        {job.data?.state === "FAILED" && (
          <p role="alert">
            Planning failed: {job.data.reason_code ?? "Please try again."}
          </p>
        )}
        {["SUPERSEDED", "CANCELLED"].includes(job.data?.state ?? "") && (
          <p>The inputs changed while planning. Generate a current plan.</p>
        )}
        {error && (
          <p role="alert" className="inline-error">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="inline-success">
            {notice}
          </p>
        )}
        {proposals.isError && (
          <p role="alert">
            Plan proposals could not be loaded.{" "}
            <button
              className="secondary"
              onClick={() => void proposals.refetch()}
            >
              Reload proposals
            </button>
          </p>
        )}
        {!candidate && !running && !proposals.isPending && (
          <p className="field-help">
            Once your tasks and available hours are ready, generate a plan to
            see where the work fits.
          </p>
        )}
        {candidate && (
          <>
            <div className="plan-status">
              <strong>
                {statusLabels[candidate.status] ?? candidate.status}
              </strong>
              <span className="subtle">
                Calendar:{" "}
                {latest?.publication_state === "SYNCED"
                  ? "synced"
                  : "not published"}
              </span>
            </div>
            {latest && !failedCandidate && !current && (
              <p className="inline-error">
                This proposal uses older inputs. Generate a new plan before
                activating.
              </p>
            )}
            {candidate.score && (
              <p className="field-help">
                Schedule score: {Math.round(candidate.score.quality * 100)} /
                100 · {candidate.source_policy}
              </p>
            )}
            {(latest?.id || (failedCandidate && jobId)) && (
              <TimeExplanation
                path={
                  failedCandidate
                    ? `/jobs/${jobId}/time-inputs`
                    : `/proposals/${latest!.id}/time-inputs`
                }
                taskNames={taskNames}
              />
            )}
            {violations.length > 0 && (
              <ul className="conflicts">
                {violations.map((violation, index) => (
                  <li key={`${violation.code}-${index}`}>
                    <strong>{conflictSummary(violation)}</strong>
                    {Object.keys(violation.facts ?? {}).length > 0 && (
                      <details>
                        <summary>Diagnostic details</summary>
                        <pre>{JSON.stringify(violation.facts, null, 2)}</pre>
                      </details>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {blocks.length > 0 && (
              <>
                {diff.data && (
                  <details>
                    <summary>Changes from the previous plan</summary>
                    <p>
                      {diff.data.retained?.length ?? 0} retained ·{" "}
                      {diff.data.moved?.length ?? 0} moved ·{" "}
                      {diff.data.added?.length ?? 0} added ·{" "}
                      {diff.data.removed?.length ?? 0} removed
                    </p>
                    <ul>
                      {diff.data.moved?.map((move) => (
                        <li key={move.new.id}>
                          {taskNames[move.new.task_id] ?? "Task"}:{" "}
                          {formatTime(move.old.start)} →{" "}
                          {formatTime(move.new.start)}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                <p className="field-help">
                  All times shown in {identity.timezone}. Scheduling uses
                  15-minute slots.
                </p>
                <ol className="schedule-blocks">
                  {blocks.map((block) => (
                    <li key={block.id}>
                      <div className="block-time">
                        {formatTime(block.start)}
                        <span>until {formatTime(block.end)}</span>
                      </div>
                      <strong>
                        {taskNames[block.task_id] ?? "Scheduled task"}
                      </strong>
                      {block.locked && <span className="subtle">Locked</span>}
                    </li>
                  ))}
                </ol>
              </>
            )}
            {latest && valid && current && !latest.activated_at && (
              <button
                disabled={busy}
                onClick={async () => {
                  if (
                    activation.current.proposal !== latest.id ||
                    activation.current.revision !== identity.revision
                  )
                    activation.current = {
                      proposal: latest.id,
                      revision: identity.revision,
                      key: crypto.randomUUID(),
                    };
                  setBusy(true);
                  setError("");
                  try {
                    await mutate(
                      `/proposals/${latest.id}/activate`,
                      "POST",
                      { expected_revision: identity.revision },
                      identity.csrf_token,
                      activation.current.key,
                    );
                    setNotice("Plan activated");
                    void cache.invalidateQueries({ queryKey: ["proposals"] });
                    onChanged();
                  } catch (failure) {
                    setError(
                      failure instanceof Error
                        ? failure.message
                        : "Plan could not be activated.",
                    );
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Activate this plan
              </button>
            )}
            {latest?.activated_at && !failedCandidate && (
              <p className="inline-success">Active plan</p>
            )}
          </>
        )}
      </div>
    </section>
  );
}
