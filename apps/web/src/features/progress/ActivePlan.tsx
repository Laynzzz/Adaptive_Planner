import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { mutate, request, type Identity } from "../../api/client";
import type { components } from "../../api/generated";
type Block = components["schemas"]["Block"];
type Protected = components["schemas"]["ProtectedItem"];

export default function ActivePlan({ identity, taskNames, onChanged }: {
  identity: Identity; taskNames: Record<string, string>; onChanged: () => void;
}) {
  const active = useQuery({ queryKey: ["active-plan", identity.id],
    queryFn: () => request<components["schemas"]["ProposalView"] | null>("/active-plan") });
  const protectedWork = useQuery({ queryKey: ["protected-work", identity.id],
    queryFn: () => request<components["schemas"]["ProtectedList"]>("/protected-work"), enabled: !!active.data });
  if (active.isError) return <p role="alert">The selected plan could not be loaded. <button className="secondary"
    onClick={() => void active.refetch()}>Reload selected plan</button></p>;
  if (!active.data) return null;
  return <details className="active-controls">
    <summary>Adjust blocks in your active plan</summary>
    <p className="field-help">Locks and moves become explicit scheduling inputs. Generate and review a new proposal after changing them.</p>
    {protectedWork.isError && <p role="alert">Block protections could not be loaded. <button className="secondary"
      onClick={() => void protectedWork.refetch()}>Reload block protections</button></p>}
    {protectedWork.data && <ul className="active-blocks">{(active.data.candidate.blocks ?? []).map((block) =>
      <li key={block.id}><h3>{taskNames[block.task_id] ?? "Scheduled task"}</h3>
        <BlockControls block={block} protectedInput={protectedWork.data.items.find((item) => item.id === block.id)}
          identity={identity} revision={protectedWork.data.revision} onChanged={onChanged} />
      </li>)}</ul>}
  </details>;
}

function BlockControls({ block, protectedInput, identity, revision, onChanged }: {
  block: Block; protectedInput?: Protected; identity: Identity; revision: number; onChanged: () => void;
}) {
  const cache = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const command = useRef({ body: "", path: "", key: "" });
  const start = protectedInput?.start ?? block.start;
  const end = protectedInput?.end ?? block.end;
  const locked = protectedInput?.locked ?? false;
  const historical = new Date(end).getTime() <= Date.now();
  async function send(action: "lock" | "move", body: Record<string, unknown>, message: string) {
    const payload = { ...body, expected_revision: revision };
    const path = `/blocks/${block.id}/${action}`; const serialized = JSON.stringify(payload);
    if (command.current.body !== serialized || command.current.path !== path)
      command.current = { path, body: serialized, key: crypto.randomUUID() };
    setBusy(true); setError(""); setNotice("");
    try {
      await mutate(path, "POST", payload, identity.csrf_token, command.current.key);
      setNotice(message); command.current = { body: "", path: "", key: "" };
      void cache.invalidateQueries({ queryKey: ["protected-work"] }); onChanged();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Block could not be changed."); }
    finally { setBusy(false); }
  }
  return <div>
    <p className="field-help">{start.replace("T", " ")} → {end.replace("T", " ")}</p>
    {protectedInput && <p className="field-help">{protectedInput.source === "IN_PROGRESS" ? "In progress with a declared end" : "Protected scheduling input"}</p>}
    {historical ? <p className="field-help">This interval is in the past. Record progress to update remaining work.</p> : <>
      <button className="secondary" disabled={busy} onClick={() => void send("lock", { locked: !locked }, locked ? "Block unlocked" : "Block locked for replanning")}>
        {locked ? "Unlock this block" : "Lock this block"}</button>
      <details><summary>Move this block</summary>
        <form aria-label="Move selected block" onSubmit={(event) => {
          event.preventDefault(); const values = new FormData(event.currentTarget);
          void send("move", { start: `${values.get("start")}:00Z`, end: `${values.get("end")}:00Z` }, "Move saved as a protected input");
        }}>
          <p className="field-help">Enter UTC times. The moved block is protected from automatic movement.</p>
          <label>New start (UTC)<input type="datetime-local" step="900" name="start" defaultValue={start.slice(0, 16)} required /></label>
          <label>New end (UTC)<input type="datetime-local" step="900" name="end" defaultValue={end.slice(0, 16)} required /></label>
          <button disabled={busy}>Save block move</button>
        </form>
      </details>
      <details><summary>Mark work in progress</summary>
        <form aria-label="Start selected block" onSubmit={(event) => {
          event.preventDefault(); const values = new FormData(event.currentTarget);
          void send("lock", { locked: true, in_progress: true, expected_end: `${values.get("end")}:00Z` }, "In-progress interval recorded");
        }}>
          <label>Expected end (UTC)<input type="datetime-local" name="end" required /></label>
          <button disabled={busy}>Start this work</button>
        </form>
      </details>
    </>}
    {error && <p role="alert" className="inline-error">{error}</p>}
    {notice && <p role="status" className="inline-success">{notice}</p>}
  </div>;
}
