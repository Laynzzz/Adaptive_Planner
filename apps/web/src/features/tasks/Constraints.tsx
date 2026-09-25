import { useRef, useState } from "react";
import { mutate, type Identity, type Task } from "../../api/client";
export default function Constraints({
  identity,
  tasks,
  onChanged,
}: {
  identity: Identity;
  tasks: Task[];
  onChanged: () => void;
}) {
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const command = useRef({ signature: "", key: "" });
  const save = async (
    path: string,
    body: Record<string, unknown>,
    message: string,
    form: HTMLFormElement,
  ) => {
    const payload = { ...body, expected_revision: identity.revision };
    const signature = JSON.stringify([path, payload]);
    if (command.current.signature !== signature)
      command.current = { signature, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await mutate(
        path,
        "POST",
        payload,
        identity.csrf_token,
        command.current.key,
      );
      form.reset();
      command.current = { signature: "", key: "" };
      setNotice(message);
      onChanged();
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Changes could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="constraints-panel">
      <details>
        <summary>Fixed commitments and task dependencies</summary>
        <form
          aria-label="Fixed commitment"
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const fields = new FormData(form);
            const start = String(fields.get("start"));
            const end = String(fields.get("end"));
            if (end <= start) {
              setError("Commitment must end after it starts.");
              return;
            }
            void save(
              "/fixed-events",
              { title: fields.get("title"), start, end },
              "Commitment added",
              form,
            );
          }}
        >
          <h3>Protect a commitment</h3>
          <p className="field-help">
            Classes, meetings, and other busy time are excluded from work slots.
          </p>
          <label>
            Commitment name
            <input name="title" required maxLength={500} />
          </label>
          <label>
            Busy from ({identity.timezone})
            <input name="start" type="datetime-local" required />
          </label>
          <label>
            Busy until ({identity.timezone})
            <input name="end" type="datetime-local" required />
          </label>
          <button disabled={busy}>Add commitment</button>
        </form>
        {tasks.length > 1 && (
          <form
            aria-label="Task dependency"
            onSubmit={(event) => {
              event.preventDefault();
              const form = event.currentTarget;
              const fields = new FormData(form);
              const predecessor = String(fields.get("predecessor"));
              const successor = String(fields.get("successor"));
              if (predecessor === successor) {
                setError("Choose two different tasks.");
                return;
              }
              void save(
                `/tasks/${successor}/dependencies`,
                { predecessor_id: predecessor },
                "Dependency added",
                form,
              );
            }}
          >
            <h3>Set the order of work</h3>
            <label>
              Finish first
              <select name="predecessor">
                {tasks.map((task) => (
                  <option key={task.id} value={task.id}>
                    {task.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Then start
              <select name="successor" defaultValue={tasks[1]?.id}>
                {tasks.map((task) => (
                  <option key={task.id} value={task.id}>
                    {task.title}
                  </option>
                ))}
              </select>
            </label>
            <button disabled={busy}>Add dependency</button>
          </form>
        )}
      </details>
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
    </div>
  );
}
