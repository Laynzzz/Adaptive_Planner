import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { mutate, request, type Identity, type Task } from "../../api/client";
import type { components } from "../../api/generated";
type Preview = components["schemas"]["WhatIfView"];
type Command = components["schemas"]["WhatIfCommand"];

export default function WhatIfPanel({ identity, tasks, onChanged }: {
  identity: Identity; tasks: Task[]; onChanged: () => void;
}) {
  const [id, setId] = useState<string | null>(null);
  const [taskId, setTaskId] = useState("");
  const [submitted, setSubmitted] = useState<Command | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [applied, setApplied] = useState(false);
  const command = useRef({ body: "", key: "" });
  const applyKey = useRef({ id: "", key: "" });
  const result = useQuery({ queryKey: ["what-if", identity.id, id],
    queryFn: () => request<Preview>(`/what-ifs/${id}`), enabled: !!id,
    refetchInterval: (query) => ["QUEUED", "RUNNING", "RETRY_WAIT"].includes(query.state.data?.state ?? "QUEUED") ? 750 : false });
  const pending = !!id && (!result.data || ["QUEUED", "RUNNING", "RETRY_WAIT"].includes(result.data.state));
  const preview = result.data;
  const stale = !!preview && preview.base_revision !== identity.revision;
  return <details className="what-if-panel">
    <summary>Explore a change before applying it</summary>
    <p className="field-help">Try a different estimate, deadline or extra work window. Your active plan stays in place while you preview.</p>
    <form aria-label="What-if inputs" onSubmit={async (event) => {
      event.preventDefault(); const data = new FormData(event.currentTarget);
      const start = String(data.get("start") ?? ""); const end = String(data.get("end") ?? "");
      if ((start && !end) || (!start && end) || (start && end <= start)) {
        setError("Extra time needs a start and a later end."); return;
      }
      const remaining = String(data.get("remaining") ?? ""); const deadline = String(data.get("deadline") ?? "");
      const patch: NonNullable<Command["task_changes"]>[number] = { task_id: taskId };
      if (remaining !== "") patch.remaining_minutes = Number(remaining);
      if (deadline) patch.deadline = { kind: "DATE", value: deadline, timezone: identity.timezone };
      const changes = taskId && (remaining !== "" || deadline) ? [patch] : [];
      if (!changes.length && !start) { setError("Choose at least one input change to preview."); return; }
      const body: Command = { expected_revision: identity.revision, task_changes: changes,
        additional_availability: start ? [{ start, end }] : [] };
      const serialized = JSON.stringify(body);
      if (command.current.body !== serialized) command.current = { body: serialized, key: crypto.randomUUID() };
      setBusy(true); setError("");
      try {
        const created = await mutate<components["schemas"]["WhatIfCreated"]>("/what-ifs", "POST", body, identity.csrf_token, command.current.key);
        setId(created.id); setSubmitted(body); setApplied(false); command.current = { body: "", key: "" };
      } catch (failure) { setError(failure instanceof Error ? failure.message : "Preview could not be created."); }
      finally { setBusy(false); }
    }}>
      <label>Task to explore<select value={taskId} onChange={(event) => setTaskId(event.target.value)}>
        <option value="">Only add available time</option>{tasks.filter((task) => !["DONE", "CANCELLED"].includes(task.state))
          .map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}</select></label>
      <label>Hypothetical remaining minutes<input type="number" min="0" step="1" name="remaining" disabled={!taskId} /></label>
      <label>Hypothetical deadline ({identity.timezone})<input type="date" name="deadline" disabled={!taskId} /></label>
      <label>Extra time from ({identity.timezone})<input type="datetime-local" step="900" name="start" /></label>
      <label>Extra time until ({identity.timezone})<input type="datetime-local" step="900" name="end" /></label>
      <button disabled={busy || pending}>{pending ? "Previewing…" : "Preview changes"}</button>
    </form>
    {error && <p role="alert" className="inline-error">{error}</p>}
    {result.isError && <p role="alert">Preview status could not be loaded. <button className="secondary"
      onClick={() => void result.refetch()}>Check preview</button></p>}
    {preview && !pending && !applied && <div className="preview-result">
      <h3>Preview result</h3>
      <ul>{submitted?.task_changes?.map((change) => <li key={change.task_id}>
        {tasks.find((task) => task.id === change.task_id)?.title ?? "Selected task"}
        {change.remaining_minutes != null ? `: ${change.remaining_minutes} minutes remaining` : ""}
        {change.deadline ? `; due ${change.deadline.value}` : ""}</li>)}
        {submitted?.additional_availability?.map((window, index) => <li key={index}>
          Extra time: {String(window.start)} → {String(window.end)} ({identity.timezone})</li>)}</ul>
      <p>{preview.candidate?.status === "INFEASIBLE" ? "These changes still cannot satisfy every constraint."
        : preview.candidate?.status === "UNKNOWN" ? "No conclusion within the search budget."
        : preview.candidate?.status === "FEASIBLE" || preview.candidate?.status === "OPTIMAL" ? "A valid preview is available."
        : `Preview state: ${preview.state}`}</p>
      {preview.diff && <p className="field-help">{preview.diff.retained?.length ?? 0} retained · {preview.diff.moved?.length ?? 0} moved · {preview.diff.added?.length ?? 0} added · {preview.diff.removed?.length ?? 0} removed</p>}
      {!!preview.candidate?.constraint_report?.length && <ul className="conflicts">{preview.candidate.constraint_report.map((violation, index) =>
        <li key={index}>{violation.code.replaceAll("_", " ").toLowerCase()}</li>)}</ul>}
      {stale && <p role="alert" className="inline-error">Inputs changed after this preview. Create a new preview before applying.</p>}
      {preview.state === "READY" && <button disabled={busy || stale || !["FEASIBLE", "OPTIMAL"].includes(preview.candidate?.status ?? "") || !!preview.candidate?.constraint_report?.length} onClick={async () => {
        if (applyKey.current.id !== preview.id) applyKey.current = { id: preview.id, key: crypto.randomUUID() };
        setBusy(true); setError("");
        try {
          await mutate(`/what-ifs/${preview.id}/apply`, "POST", { expected_revision: preview.base_revision }, identity.csrf_token, applyKey.current.key);
          setApplied(true); onChanged();
        } catch (failure) { setError(failure instanceof Error ? failure.message : "Changes could not be applied."); }
        finally { setBusy(false); }
      }}>Apply these input changes</button>}
    </div>}
    {applied && <p role="status" className="inline-success">Inputs updated. Review and activate the new plan when it is ready.</p>}
  </details>;
}
