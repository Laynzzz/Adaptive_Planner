import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { mutate, request, type Identity } from "../../api/client";
import type { components } from "../../api/generated";

export default function CalendarPanel({ identity, onChanged }: { identity: Identity; onChanged: () => void }) {
  const cache = useQueryClient();
  const status = useQuery({ queryKey: ["calendar", identity.id],
    queryFn: () => request<components["schemas"]["CalendarStatusView"]>("/calendar/status"), refetchInterval: 2000 });
  const [provider, setProvider] = useState("MOCK");
  const [confirmed, setConfirmed] = useState(false);
  const [keepEvents, setKeepEvents] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const command = useRef({ path: "", body: "", key: "" });
  async function send(path: string, fields: Record<string, unknown>, message: string) {
    const body = { ...fields, expected_revision: status.data!.revision };
    const serialized = JSON.stringify(body);
    if (command.current.path !== path || command.current.body !== serialized)
      command.current = { path, body: serialized, key: crypto.randomUUID() };
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await mutate<components["schemas"]["CalendarCommandView"]>(path, "POST", body, identity.csrf_token, command.current.key);
      setNotice(message); command.current = { path: "", body: "", key: "" };
      void cache.invalidateQueries({ queryKey: ["calendar"] }); onChanged();
      if (response.authorization_url) window.location.assign(response.authorization_url);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Calendar action failed."); }
    finally { setBusy(false); }
  }
  const calendar = status.data;
  return <details className="calendar-panel">
    <summary>Calendar export and connection</summary>
    <p className="field-help"><a href="/api/v1/exports/calendar.ics" download>Download active plan as ICS</a></p>
    <p className="field-help">ICS is a one-time copy. A connected calendar is reconciled separately from your local plan.</p>
    {status.isError && <p role="alert">Calendar status could not be loaded. <button className="secondary"
      onClick={() => void status.refetch()}>Reload calendar</button></p>}
    {calendar && <>
      <p>Connection: {calendar.state.toLowerCase().replaceAll("_", " ")}{calendar.provider === "MOCK" ? " · Local simulator" : calendar.provider === "GOOGLE" ? " · Google Calendar" : ""}</p>
      {!calendar.live_configured && <p className="field-help">Live Google access is not configured. The local simulator makes no Google requests.</p>}
      {calendar.error_code && <p role="alert" className="inline-error">Calendar needs attention: {calendar.error_code.replaceAll("_", " ").toLowerCase()}</p>}
      {["DISCONNECTED", "NEEDS_REAUTH"].includes(calendar.state) && <form aria-label="Connect calendar" onSubmit={(event) => {
        event.preventDefault(); const fields = new FormData(event.currentTarget);
        void send("/calendar/connect", { provider, calendar_id: fields.get("calendar_id"), dedicated_synthetic_confirmed: confirmed }, "Calendar connection saved");
      }}>
        <label>Calendar provider<select value={provider} onChange={(event) => setProvider(event.target.value)}>
          <option value="MOCK">Local calendar simulator</option><option value="GOOGLE" disabled={!calendar.live_configured}>Google Calendar</option>
        </select></label>
        <label>Dedicated calendar ID<input name="calendar_id" required defaultValue={calendar.calendar_id ?? "adaptive-planner-demo"} /></label>
        <label className="checkbox-field"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />This is a dedicated calendar for synthetic tasks</label>
        <button disabled={busy || !confirmed}>Connect calendar</button>
      </form>}
      {calendar.state === "CONNECTED" && <>
        <p role="status">{calendar.published_count} published · {calendar.pending_count} pending
          {calendar.sync_pending ? " · Sync queued" : ""}{calendar.publish_pending ? " · Publication queued" : ""}</p>
        <div className="button-group">
          <button className="secondary" disabled={busy || calendar.sync_pending} onClick={() => void send("/calendar/sync", {}, "Calendar synchronization queued")}>Sync calendar</button>
          <button className="secondary" disabled={busy || calendar.publish_pending} onClick={() => void send("/calendar/publish", {}, "Calendar publication queued")}>Publish active plan</button>
        </div>
      </>}
      {(calendar.conflicts ?? []).map((conflict) => <section key={conflict.id} className="calendar-conflict">
        <h3>Calendar conflict</h3><p>{conflict.reason.replaceAll("_", " ").toLowerCase()}</p>
        <p className="field-help">Choose how to resolve this remote change. The original event is not silently overwritten.</p>
        <div className="button-group">
          <button disabled={busy} onClick={() => void send(`/calendar/conflicts/${conflict.id}/resolve`, { action: "RESTORE" }, "Restore requested")}>Restore planned event</button>
          {conflict.reason.includes("DELETION") ? <button className="secondary" disabled={busy} onClick={() => void send(`/calendar/conflicts/${conflict.id}/resolve`, { action: "ACCEPT_DELETION" }, "Deletion accepted; remaining work can be replanned")}>Accept deletion</button>
            : <button className="secondary" disabled={busy} onClick={() => void send(`/calendar/conflicts/${conflict.id}/resolve`, { action: "REMOVE_COMMITMENT" }, "Manual commitment removed")}>Release moved commitment</button>}
        </div>
      </section>)}
      {["CONNECTED", "NEEDS_REAUTH", "AUTHORIZING"].includes(calendar.state) && <details><summary>Disconnect calendar</summary>
        <label className="checkbox-field"><input type="checkbox" checked={keepEvents} onChange={(event) => setKeepEvents(event.target.checked)} />Keep remote events after disconnecting</label>
        <p className="field-help">If unchecked, only unchanged events owned by this planner are eligible for removal. Manual edits stay protected.</p>
        <button className="secondary" disabled={busy} onClick={() => void send("/calendar/disconnect", { keep_remote_events: keepEvents }, "Calendar disconnection queued")}>Confirm disconnect</button>
      </details>}
    </>}
    {error && <p role="alert" className="inline-error">{error}</p>}
    {notice && <p role="status" className="inline-success">{notice}</p>}
  </details>;
}
