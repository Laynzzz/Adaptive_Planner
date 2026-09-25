import { useRef, useState } from "react";
import { mutate, type Identity } from "../../api/client";

export default function TaskForm({
  identity,
  onSaved,
}: {
  identity: Identity;
  onSaved: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const errorRef = useRef<HTMLParagraphElement>(null);
  const command = useRef({ body: "", key: "" });
  return (
    <form
      aria-label="Add task"
      className="task-form"
      onSubmit={async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const fields = new FormData(form);
        const deadline = fields.get("deadline") as string;
        const body = {
          title: (fields.get("title") as string).trim(),
          remaining_minutes: Number(fields.get("remaining_minutes")),
          priority: Number(fields.get("priority")),
          splittable: fields.get("splittable") === "on",
          min_block_slots: Number(fields.get("min_block_slots")),
          max_block_slots: Number(fields.get("max_block_slots")),
          short_final_allowed: fields.get("short_final_allowed") === "on",
          deadline: deadline
            ? { kind: "DATE", value: deadline, timezone: identity.timezone }
            : null,
          expected_revision: identity.revision,
        };
        const serialized = JSON.stringify(body);
        if (command.current.body !== serialized)
          command.current = { body: serialized, key: crypto.randomUUID() };
        setBusy(true);
        setError("");
        setSaved(false);
        try {
          await mutate(
            "/tasks",
            "POST",
            body,
            identity.csrf_token,
            command.current.key,
          );
          form.reset();
          command.current = { body: "", key: "" };
          setSaved(true);
          onSaved();
        } catch (failure) {
          setError(
            failure instanceof Error
              ? failure.message
              : "Task could not be saved.",
          );
          requestAnimationFrame(() => errorRef.current?.focus());
        } finally {
          setBusy(false);
        }
      }}
    >
      <h2>Add a task</h2>
      <label>
        Task name
        <input
          name="title"
          required
          maxLength={500}
          placeholder="e.g. Write lab report"
        />
      </label>
      <div className="field-row">
        <label>
          Remaining minutes
          <input
            name="remaining_minutes"
            type="number"
            min="1"
            max="20160"
            step="1"
            defaultValue="60"
            required
          />
        </label>
        <label>
          Deadline ({identity.timezone})<input name="deadline" type="date" />
        </label>
      </div>
      <p className="field-help">
        Date deadlines include that whole day. Effort rounds up to 15-minute
        slots.
      </p>
      <label>
        Priority
        <select name="priority" defaultValue="3">
          <option value="1">1 · Low</option>
          <option value="2">2</option>
          <option value="3">3 · Normal</option>
          <option value="4">4</option>
          <option value="5">5 · High</option>
        </select>
      </label>
      <details>
        <summary>Work block preferences</summary>
        <label className="checkbox-field">
          <input name="splittable" type="checkbox" defaultChecked /> Allow more
          than one work block
        </label>
        <div className="field-row">
          <label>
            Minimum block
            <select name="min_block_slots" defaultValue="2">
              <option value="1">15 minutes</option>
              <option value="2">30 minutes</option>
              <option value="4">60 minutes</option>
            </select>
          </label>
          <label>
            Maximum block
            <select name="max_block_slots" defaultValue="12">
              <option value="4">60 minutes</option>
              <option value="8">120 minutes</option>
              <option value="12">180 minutes</option>
            </select>
          </label>
        </div>
        <label className="checkbox-field">
          <input name="short_final_allowed" type="checkbox" /> Allow a shorter
          final block (at least 15 minutes)
        </label>
      </details>
      {error && (
        <p className="inline-error" role="alert" ref={errorRef} tabIndex={-1}>
          {error}
        </p>
      )}
      {saved && (
        <p className="inline-success" role="status">
          Task added
        </p>
      )}
      <button type="submit" disabled={busy}>
        {busy ? "Saving…" : "Add task"}
      </button>
    </form>
  );
}
