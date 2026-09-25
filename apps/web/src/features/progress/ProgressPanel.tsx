import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { mutate, request, type Identity, type Task } from "../../api/client";
import type { components } from "../../api/generated";

export default function ProgressPanel({ identity, tasks, onChanged }: {
  identity: Identity; tasks: Task[]; onChanged: () => void;
}) {
  const cache = useQueryClient();
  const [taskId, setTaskId] = useState("");
  const [correction, setCorrection] = useState("");
  const [complete, setComplete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const command = useRef({ body: "", key: "", path: "" });
  const logs = useQuery({ queryKey: ["work-logs", identity.id, taskId],
    queryFn: () => request<components["schemas"]["WorkLogList"]>(`/tasks/${taskId}/work-logs`), enabled: !!taskId });
  return <details className="progress-panel">
    <summary>Record progress or missed work</summary>
    <p className="field-help">Enter the time you actually spent, then estimate what is left.
      For missed work, record zero minutes and confirm your remaining estimate.</p>
    <form aria-label="Record progress" onSubmit={async (event) => {
      event.preventDefault(); const form = event.currentTarget; const values = new FormData(form);
      const body = { observed_minutes: Number(values.get("observed")),
        new_remaining_minutes: complete ? 0 : Number(values.get("remaining")), complete,
        expected_revision: identity.revision };
      const path = correction ? `/work-logs/${correction}/corrections` : `/tasks/${taskId}/work-logs`;
      const serialized = JSON.stringify(body);
      if (command.current.body !== serialized || command.current.path !== path)
        command.current = { path, body: serialized, key: crypto.randomUUID() };
      setBusy(true); setError(""); setNotice("");
      try {
        await mutate(path, "POST", body, identity.csrf_token, command.current.key);
        setNotice(correction ? "Correction recorded; the original log is preserved" : "Progress recorded");
        setCorrection(""); setComplete(false); form.reset();
        command.current = { body: "", key: "", path: "" };
        void cache.invalidateQueries({ queryKey: ["work-logs"] }); onChanged();
      } catch (failure) { setError(failure instanceof Error ? failure.message : "Progress could not be recorded."); }
      finally { setBusy(false); }
    }}>
      <label>Task to update<select required value={taskId} onChange={(event) => {
        setTaskId(event.target.value); setCorrection(""); setNotice(""); setComplete(false);
      }}><option value="">Choose a task</option>{tasks.filter((task) => task.state !== "CANCELLED")
        .map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}</select></label>
      {correction && <p className="field-help">Correcting an earlier observation. Its original values remain in the history.
        <button type="button" className="secondary" onClick={() => setCorrection("")}>Cancel correction</button></p>}
      <label>Observed time (minutes)<input name="observed" type="number" min="0" step="1" defaultValue="0" required /></label>
      <label>New remaining estimate (minutes)<input name="remaining" type="number" min="0" step="1" required={!complete} disabled={complete} /></label>
      <label className="checkbox-field"><input type="checkbox" checked={complete}
        onChange={(event) => setComplete(event.target.checked)} />Mark task complete</label>
      <button disabled={busy || !taskId}>{busy ? "Saving…" : correction ? "Save correction" : "Save progress"}</button>
    </form>
    {error && <p role="alert" className="inline-error">{error}</p>}
    {notice && <p role="status" className="inline-success">{notice}</p>}
    {logs.isError && <p role="alert">Progress history could not be loaded. <button className="secondary"
      onClick={() => void logs.refetch()}>Reload progress</button></p>}
    {!!logs.data?.items.length && <ol className="progress-history">{logs.data.items.map((log) => <li key={log.id}>
      <p>{log.observed_minutes} minutes observed · {log.new_remaining_minutes} minutes remaining
        {log.complete ? " · Completed" : ""}{log.correction_of ? " · Correction" : ""}</p>
      <button type="button" className="secondary" onClick={() => { setCorrection(log.id); setComplete(log.complete); }}>
        Correct this entry</button>
    </li>)}</ol>}
  </details>;
}
