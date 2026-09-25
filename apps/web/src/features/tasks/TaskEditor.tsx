import { useId, useRef, useState } from "react";
import { mutate, type Identity, type Task } from "../../api/client";

export default function TaskEditor({
  identity,
  task,
  onChanged,
}: {
  identity: Identity;
  task: Task;
  onChanged: () => void;
}) {
  const formId = useId();
  const [snapshot, setSnapshot] = useState<Task | null>(null);
  const [deadlineKind, setDeadlineKind] = useState("NONE");
  const [busy, setBusy] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [error, setError] = useState("");
  const errorRef = useRef<HTMLParagraphElement>(null);
  const command = useRef({ body: "", key: "" });
  if (task.state === "DONE" || task.state === "CANCELLED") return null;
  async function send(path: string, method: string, body: unknown) {
    const serialized = JSON.stringify({ path, method, body });
    if (command.current.body !== serialized)
      command.current = { body: serialized, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    try {
      await mutate(
        path,
        method,
        body,
        identity.csrf_token,
        command.current.key,
      );
      setSnapshot(null);
      command.current = { body: "", key: "" };
      onChanged();
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Task could not be changed.",
      );
      requestAnimationFrame(() => errorRef.current?.focus());
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="task-editor">
      <button
        type="button"
        className="secondary"
        aria-label={`Edit task ${task.title}`}
        aria-expanded={snapshot !== null}
        aria-controls={formId}
        disabled={busy}
        onClick={() => {
          setSnapshot(snapshot ? null : task);
          setDeadlineKind(task.deadline?.kind ?? "NONE");
          setConfirmCancel(false);
          setError("");
        }}
      >
        {snapshot ? "Close editor" : "Edit task"}
      </button>
      {snapshot && (
        <form
          id={formId}
          aria-label={`Edit ${snapshot.title}`}
          className="task-form"
          onSubmit={async (event) => {
            event.preventDefault();
            const fields = new FormData(event.currentTarget);
            const value = String(fields.get("deadline") ?? "");
            const deadline =
              deadlineKind === "NONE"
                ? null
                : snapshot.deadline?.kind === deadlineKind &&
                    snapshot.deadline.value === value
                  ? snapshot.deadline
                  : { kind: deadlineKind, value, timezone: identity.timezone };
            await send(`/tasks/${snapshot.id}`, "PATCH", {
              expected_revision: snapshot.revision,
              title: String(fields.get("title")).trim(),
              priority: Number(fields.get("priority")),
              deadline,
              splittable: fields.get("splittable") === "on",
              min_block_slots: Number(fields.get("min_block_slots")),
              max_block_slots: Number(fields.get("max_block_slots")),
              short_final_allowed: fields.get("short_final_allowed") === "on",
            });
          }}
        >
          <label>
            Task title
            <input
              name="title"
              required
              maxLength={500}
              defaultValue={snapshot.title}
            />
          </label>
          <label>
            Priority
            <select name="priority" defaultValue={snapshot.priority}>
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label>
            Deadline type
            <select
              value={deadlineKind}
              onChange={(event) => setDeadlineKind(event.target.value)}
            >
              <option value="NONE">No deadline</option>
              <option value="DATE">Whole day</option>
              <option value="TIMESTAMP">Exact time</option>
            </select>
          </label>
          {deadlineKind !== "NONE" && (
            <label>
              Deadline ({identity.timezone})
              <input
                key={deadlineKind}
                name="deadline"
                required
                type={deadlineKind === "DATE" ? "date" : "text"}
                placeholder={
                  deadlineKind === "TIMESTAMP"
                    ? "2026-09-30T17:00:00Z"
                    : undefined
                }
                defaultValue={
                  snapshot.deadline?.kind === deadlineKind
                    ? snapshot.deadline.value
                    : ""
                }
              />
            </label>
          )}
          {deadlineKind === "TIMESTAMP" && (
            <p className="field-help">
              Enter an ISO time with its offset, such as 2026-09-30T17:00:00Z.
            </p>
          )}
          <label className="checkbox-field">
            <input
              type="checkbox"
              name="splittable"
              defaultChecked={snapshot.splittable}
            />
            Allow more than one work block
          </label>
          <div className="field-row">
            <label>
              Minimum block (15-minute slots)
              <input
                type="number"
                name="min_block_slots"
                required
                min={1}
                max={12}
                step={1}
                defaultValue={snapshot.min_block_slots}
              />
            </label>
            <label>
              Maximum block (15-minute slots)
              <input
                type="number"
                name="max_block_slots"
                required
                min={2}
                max={12}
                step={1}
                defaultValue={snapshot.max_block_slots}
              />
            </label>
          </div>
          <label className="checkbox-field">
            <input
              type="checkbox"
              name="short_final_allowed"
              defaultChecked={snapshot.short_final_allowed}
            />
            Allow a shorter final block
          </label>
          <p className="field-help">
            Record progress separately to revise remaining effort.
          </p>
          {error && (
            <p
              role="alert"
              className="inline-error"
              ref={errorRef}
              tabIndex={-1}
            >
              {error}
            </p>
          )}
          <button disabled={busy} type="submit">
            {busy ? "Saving…" : "Save task changes"}
          </button>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={confirmCancel}
              onChange={(event) => setConfirmCancel(event.target.checked)}
            />
            I want to cancel this task
          </label>
          <button
            type="button"
            className="secondary"
            disabled={busy || !confirmCancel}
            onClick={() =>
              send(`/tasks/${snapshot.id}/cancel`, "POST", {
                expected_revision: snapshot.revision,
              })
            }
          >
            Cancel task
          </button>
        </form>
      )}
    </div>
  );
}
