import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { mutate, request, type Identity } from "../../api/client";
import type { components } from "../../api/generated";

type Interpretation = components["schemas"]["InterpretationView"];
type DraftTask = components["schemas"]["DraftTask"];
const fields = ["title", "remaining_minutes", "deadline", "priority"] as const;
const labels = {
  title: "Task name",
  remaining_minutes: "Remaining minutes",
  deadline: "Deadline date",
  priority: "Priority",
};

export default function InterpretationPanel({
  identity,
  onChanged,
}: {
  identity: Identity;
  onChanged: () => void;
}) {
  const [source, setSource] = useState("");
  const [id, setId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [accepted, setAccepted] = useState(false);
  const command = useRef({ body: "", key: "" });
  const result = useQuery({
    queryKey: ["interpretation", identity.id, id],
    queryFn: () => request<Interpretation>(`/interpretations/${id}`),
    enabled: !!id,
    refetchInterval: (query) =>
      ["QUEUED", "RUNNING"].includes(query.state.data?.state ?? "QUEUED")
        ? 750
        : false,
  });
  const pending =
    !!id &&
    !accepted &&
    (!result.data || ["QUEUED", "RUNNING"].includes(result.data.state));
  return (
    <details className="interpretation-panel">
      <summary>Describe tasks in your own words</summary>
      <p className="field-help">
        Local demo extraction. Review each field before adding tasks. No live AI
        provider is connected.
      </p>
      <form
        aria-label="Extract tasks"
        onSubmit={async (event) => {
          event.preventDefault();
          const body = {
            text: source,
            expected_revision: identity.revision,
            mode: "mock",
          };
          const serialized = JSON.stringify(body);
          if (command.current.body !== serialized)
            command.current = { body: serialized, key: crypto.randomUUID() };
          setBusy(true);
          setError("");
          try {
            const queued = await mutate<{ id: string }>(
              "/interpretations",
              "POST",
              body,
              identity.csrf_token,
              command.current.key,
            );
            setId(queued.id);
            setAccepted(false);
            command.current = { body: "", key: "" };
          } catch (failure) {
            setError(
              failure instanceof Error ? failure.message : "Extraction failed.",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Describe your tasks
          <textarea
            required
            maxLength={8000}
            rows={4}
            value={source}
            onChange={(event) => setSource(event.target.value)}
            placeholder="Review chapter, 60 minutes, due 2026-10-02"
          />
        </label>
        <button disabled={busy || pending}>
          {pending ? "Extracting…" : "Extract draft"}
        </button>
      </form>
      <p className="field-help">
        <a href="#manual-task-form">Use the task form</a> at any time.
      </p>
      {error && (
        <p role="alert" className="inline-error">
          {error}
        </p>
      )}
      {result.isError && (
        <p role="alert">
          The extraction status could not be loaded.{" "}
          <button className="secondary" onClick={() => void result.refetch()}>
            Check extraction
          </button>
        </p>
      )}
      {result.data?.state === "FAILED" && (
        <p role="alert" className="inline-error">
          Extraction could not finish ({result.data.error_code}). Your text is
          still available for manual entry.
        </p>
      )}
      {accepted && (
        <p role="status" className="inline-success">
          {result.data?.proposal?.constraints?.length
            ? "Reviewed inputs added"
            : "Reviewed tasks added"}
        </p>
      )}
      {!accepted && result.data?.state === "READY" && (
        <Review
          key={result.data.id}
          interpretation={result.data}
          identity={identity}
          onAccepted={() => {
            setAccepted(true);
            onChanged();
          }}
        />
      )}
    </details>
  );
}

function Review({
  interpretation,
  identity,
  onAccepted,
}: {
  interpretation: Interpretation;
  identity: Identity;
  onAccepted: () => void;
}) {
  const tasks = interpretation.proposal?.tasks ?? [];
  const constraints = interpretation.proposal?.constraints ?? [];
  const [selected, setSelected] = useState(tasks.map((task) => task.key));
  const [selectedConstraints, setSelectedConstraints] = useState(
    constraints.map((rule) => rule.key),
  );
  const [overrides, setOverrides] = useState<Record<string, unknown>>({});
  const [confirmed, setConfirmed] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const command = useRef({ body: "", key: "" });
  const path = (task: DraftTask, field: (typeof fields)[number]) =>
    `tasks.${task.key}.${field}`;
  const update = (key: string, value: unknown) =>
    setOverrides((current) => ({ ...current, [key]: value }));
  const selectedTasks = tasks.filter((task) => selected.includes(task.key));
  const unresolved = selectedTasks.some((task) =>
    fields.some((field) => {
      const key = path(task, field);
      if (key in overrides)
        return (
          field !== "deadline" &&
          (overrides[key] === "" || overrides[key] === null)
        );
      return (
        task[field].label === "unknown" ||
        (task[field].requires_confirmation && !confirmed.includes(key))
      );
    }),
  );
  const unresolvedConstraints = selectedConstraints.some(
    (key) => !confirmed.includes(`constraints.${key}`),
  );
  const stale = interpretation.planning_revision !== identity.revision;
  return (
    <form
      aria-label="Review extracted tasks"
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        setError("");
        const allowed = new Set([
          ...selectedTasks.flatMap((task) =>
            fields.map((field) => path(task, field)),
          ),
          ...selectedConstraints.map((key) => `constraints.${key}`),
        ]);
        const body = {
          expected_revision: interpretation.planning_revision,
          selected_task_keys: selected,
          selected_constraint_keys: selectedConstraints,
          confirmed_fields: confirmed.filter((key) => allowed.has(key)),
          overrides: Object.fromEntries(
            Object.entries(overrides).filter(([key]) => allowed.has(key)),
          ),
        };
        const serialized = JSON.stringify(body);
        if (command.current.body !== serialized)
          command.current = { body: serialized, key: crypto.randomUUID() };
        try {
          await mutate(
            `/interpretations/${interpretation.id}/accept`,
            "POST",
            body,
            identity.csrf_token,
            command.current.key,
          );
          onAccepted();
        } catch (failure) {
          setError(
            failure instanceof Error
              ? failure.message
              : "Review could not be accepted.",
          );
        } finally {
          setBusy(false);
        }
      }}
    >
      <h3>Review the extracted draft</h3>
      <blockquote className="source-text">
        {interpretation.source_text}
      </blockquote>
      {stale && (
        <p role="alert" className="inline-error">
          Your inputs changed. Extract a fresh draft before accepting.
        </p>
      )}
      {constraints.length > 0 && (
        <fieldset>
          <legend>Review weekday rules</legend>
          {constraints.map((rule) => {
            const key = `constraints.${rule.key}`;
            const label = `${rule.kind === "SOFT_AVOID" ? "Prefer to avoid work" : rule.kind === "HARD_UNAVAILABLE" ? "Cannot work" : "No task deadlines"} on ${["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][rule.weekday]}`;
            return (
              <div className="review-field" key={rule.key}>
                <label className="checkbox-field">
                  <input
                    type="checkbox"
                    checked={selectedConstraints.includes(rule.key)}
                    onChange={(event) =>
                      setSelectedConstraints(
                        event.target.checked
                          ? [...selectedConstraints, rule.key]
                          : selectedConstraints.filter(
                              (item) => item !== rule.key,
                            ),
                      )
                    }
                  />
                  {label}
                </label>
                <p className="field-help">
                  {rule.kind === "SOFT_AVOID"
                    ? "Preference: work can still be scheduled if needed."
                    : "Hard rule: schedules and inputs must satisfy this restriction."}
                  {rule.evidence.map((span, i) => (
                    <q key={i}>{span.text}</q>
                  ))}
                </p>
                <label className="checkbox-field">
                  <input
                    type="checkbox"
                    checked={confirmed.includes(key)}
                    disabled={!selectedConstraints.includes(rule.key)}
                    onChange={(event) =>
                      setConfirmed(
                        event.target.checked
                          ? [...confirmed, key]
                          : confirmed.filter((item) => item !== key),
                      )
                    }
                  />
                  Confirm {label}
                </label>
              </div>
            );
          })}
        </fieldset>
      )}
      {tasks.length === 0 && constraints.length === 0 && (
        <p>
          No tasks or rules could be extracted reliably. Use manual entry or
          clarify your text.
        </p>
      )}
      {tasks.map((task, index) => (
        <fieldset key={task.key} aria-label={`Review task ${index + 1}`}>
          <legend>Task {index + 1}</legend>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={selected.includes(task.key)}
              onChange={(event) =>
                setSelected(
                  event.target.checked
                    ? [...selected, task.key]
                    : selected.filter((key) => key !== task.key),
                )
              }
            />
            Include this task
          </label>
          {fields.map((field) => {
            const extracted = task[field];
            const key = path(task, field);
            const value = key in overrides ? overrides[key] : extracted.value;
            const display =
              field === "deadline"
                ? ((value as { value?: string } | null)?.value ?? "").slice(
                    0,
                    10,
                  )
                : String(value ?? "");
            return (
              <div className="review-field" key={key}>
                <label>
                  {labels[field]}
                  <input
                    type={
                      field === "deadline"
                        ? "date"
                        : ["priority", "remaining_minutes"].includes(field)
                          ? "number"
                          : "text"
                    }
                    value={display}
                    min={
                      field === "priority" || field === "remaining_minutes"
                        ? 1
                        : undefined
                    }
                    max={field === "priority" ? 5 : undefined}
                    disabled={!selected.includes(task.key)}
                    onChange={(event) =>
                      update(
                        key,
                        field === "deadline"
                          ? event.target.value
                            ? {
                                kind: "DATE",
                                value: event.target.value,
                                timezone: interpretation.timezone,
                              }
                            : null
                          : field === "title"
                            ? event.target.value
                            : event.target.value
                              ? Number(event.target.value)
                              : "",
                      )
                    }
                  />
                </label>
                <p className="field-help">
                  {extracted.label === "explicit"
                    ? "From your text"
                    : extracted.label === "inferred"
                      ? "Inferred — confirm or edit"
                      : "Unknown — enter your choice"}
                  {extracted.evidence.map((span, i) => (
                    <q key={i}>{span.text}</q>
                  ))}
                </p>
                {field === "deadline" && (
                  <label className="checkbox-field">
                    <input
                      type="checkbox"
                      checked={key in overrides && overrides[key] === null}
                      disabled={!selected.includes(task.key)}
                      onChange={(event) =>
                        event.target.checked
                          ? update(key, null)
                          : setOverrides((current) => {
                              const next = { ...current };
                              delete next[key];
                              return next;
                            })
                      }
                    />
                    Use no deadline
                  </label>
                )}
                {extracted.requires_confirmation &&
                  extracted.label !== "unknown" &&
                  !(key in overrides) && (
                    <label className="checkbox-field">
                      <input
                        type="checkbox"
                        checked={confirmed.includes(key)}
                        disabled={!selected.includes(task.key)}
                        onChange={(event) =>
                          setConfirmed(
                            event.target.checked
                              ? [...confirmed, key]
                              : confirmed.filter((item) => item !== key),
                          )
                        }
                      />
                      Confirm {labels[field]}
                    </label>
                  )}
              </div>
            );
          })}
        </fieldset>
      ))}
      {error && (
        <p role="alert" className="inline-error">
          {error}
        </p>
      )}
      <button
        disabled={
          busy ||
          unresolved ||
          unresolvedConstraints ||
          selected.length + selectedConstraints.length === 0 ||
          stale
        }
      >
        {busy
          ? "Adding…"
          : constraints.length
            ? "Add reviewed inputs"
            : "Add reviewed tasks"}
      </button>
    </form>
  );
}
