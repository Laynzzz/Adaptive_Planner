import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import {
  ApiError,
  mutate,
  request,
  showInstant,
  type Identity,
  type Task,
} from "../../api/client";
import type { components } from "../../api/generated";

export default function Commitments({
  identity,
  tasks,
  onChanged,
}: {
  identity: Identity;
  tasks: Task[];
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const events = useQuery({
    queryKey: ["fixed-events", identity.id],
    queryFn: () =>
      request<components["schemas"]["FixedEventPage"]>("/fixed-events"),
    enabled: open,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const command = useRef({ signature: "", key: "" });
  async function save(
    path: string,
    method: string,
    body: Record<string, unknown>,
  ) {
    const signature = JSON.stringify([path, method, body]);
    if (command.current.signature !== signature)
      command.current = { signature, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await mutate(
        path,
        method,
        body,
        identity.csrf_token,
        command.current.key,
      );
      command.current = { signature: "", key: "" };
      setNotice("Commitments updated");
      await events.refetch();
      onChanged();
      return true;
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Commitment could not be changed.",
      );
      if (failure instanceof ApiError && failure.status === 409) {
        await events.refetch();
        onChanged();
      }
      return false;
    } finally {
      setBusy(false);
    }
  }
  const names = Object.fromEntries(tasks.map((task) => [task.id, task.title]));
  return (
    <details
      className="interpretation-panel"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>Review existing commitments</summary>
      <p className="field-help">
        Edit or remove busy time and dependencies when your plans change. Every
        change creates a new planning revision.
      </p>
      {events.isPending && open && <p role="status">Loading commitments…</p>}
      {events.isError && (
        <p role="alert">
          Commitments could not be loaded.{" "}
          <button onClick={() => void events.refetch()}>Retry</button>
        </p>
      )}
      <ul>
        {events.data?.items?.map((event) => (
          <li key={event.id}>
            <strong>{event.title}</strong>
            <p>
              {showInstant(event.start)} → {showInstant(event.end)}
            </p>
            <button
              className="secondary"
              disabled={busy}
              aria-label={`Remove commitment ${event.title}`}
              onClick={() =>
                void save(`/fixed-events/${event.id}`, "DELETE", {
                  expected_revision: events.data!.revision,
                })
              }
            >
              Remove commitment
            </button>
            <CommitmentEditor
              event={event}
              revision={events.data!.revision}
              timezone={identity.timezone}
              busy={busy}
              save={save}
            />
          </li>
        ))}
      </ul>
      <h3>Task dependencies</h3>
      <ul>
        {tasks.flatMap((task) =>
          (task.predecessor_ids ?? []).map((predecessor) => (
            <li key={`${task.id}-${predecessor}`}>
              {names[predecessor] ?? "Predecessor"} must finish before{" "}
              {task.title}.{" "}
              <button
                className="secondary"
                disabled={busy}
                aria-label={`Remove dependency for ${task.title}`}
                onClick={() =>
                  void save(
                    `/tasks/${task.id}/dependencies/${predecessor}`,
                    "DELETE",
                    { expected_revision: task.revision },
                  )
                }
              >
                Remove dependency
              </button>
            </li>
          )),
        )}
      </ul>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </details>
  );
}

function CommitmentEditor({
  event,
  revision,
  timezone,
  busy,
  save,
}: {
  event: { id: string; title: string };
  revision: number;
  timezone: string;
  busy: boolean;
  save: (
    path: string,
    method: string,
    body: Record<string, unknown>,
  ) => Promise<boolean>;
}) {
  const [draft, setDraft] = useState<{
    title: string;
    revision: number;
    timezone: string;
  } | null>(null);
  return (
    <details
      open={draft !== null}
      onToggle={(action) => {
        if (action.currentTarget.open && !draft)
          setDraft({ title: event.title, revision, timezone });
        else if (!action.currentTarget.open) setDraft(null);
      }}
    >
      <summary>Edit {draft?.title ?? event.title}</summary>
      {draft && (
        <form
          onSubmit={async (action) => {
            action.preventDefault();
            const fields = new FormData(action.currentTarget);
            const body: Record<string, unknown> = {
              title: fields.get("title"),
              expected_revision: draft.revision,
            };
            if (fields.get("start")) body.start = fields.get("start");
            if (fields.get("end")) body.end = fields.get("end");
            if (await save(`/fixed-events/${event.id}`, "PATCH", body))
              setDraft(null);
          }}
        >
          <label>
            Commitment title
            <input
              name="title"
              defaultValue={draft.title}
              maxLength={500}
              required
            />
          </label>
          <p className="field-help">
            Leave a time blank to keep its current value. If the plan changed,
            close and reopen this editor to review current values before saving
            again.
          </p>
          <label>
            New busy from ({draft.timezone})
            <input type="datetime-local" name="start" />
          </label>
          <label>
            New busy until ({draft.timezone})
            <input type="datetime-local" name="end" />
          </label>
          <button disabled={busy}>Save commitment changes</button>
        </form>
      )}
    </details>
  );
}
