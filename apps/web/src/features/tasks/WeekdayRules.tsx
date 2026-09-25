import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { ApiError, mutate, request, type Identity } from "../../api/client";
import type { components } from "../../api/generated";

const days = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];
const strengths = {
  SOFT_AVOID: "Prefer to keep free",
  HARD_UNAVAILABLE: "Never schedule work",
  HARD_NO_DEADLINE: "Do not allow deadlines",
};
export default function WeekdayRules({
  identity,
  onChanged,
}: {
  identity: Identity;
  onChanged: () => void;
}) {
  const rules = useQuery({
    queryKey: ["weekday-rules", identity.id],
    queryFn: () => request<components["schemas"]["RuleList"]>("/weekday-rules"),
  });
  const [kind, setKind] = useState<keyof typeof strengths>("SOFT_AVOID");
  const [weekday, setWeekday] = useState(6);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const pending = useRef({ signature: "", key: "" });
  async function save(id?: string) {
    if (!rules.data) return;
    const body = id
      ? { expected_revision: rules.data.revision }
      : { kind, weekday, expected_revision: rules.data.revision };
    const signature = JSON.stringify([id, body]);
    if (pending.current.signature !== signature)
      pending.current = { signature, key: crypto.randomUUID() };
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await mutate(
        `/weekday-rules${id ? "/" + id : ""}`,
        id ? "DELETE" : "POST",
        body,
        identity.csrf_token,
        pending.current.key,
      );
      pending.current = { signature: "", key: "" };
      setNotice(id ? "Weekly rule removed" : "Weekly rule saved");
      await rules.refetch();
      onChanged();
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Weekly rule could not be saved.",
      );
      if (failure instanceof ApiError && failure.status === 409) {
        await rules.refetch();
        onChanged();
      }
    } finally {
      setSaving(false);
    }
  }
  return (
    <details className="interpretation-panel">
      <summary>Weekly preferences</summary>
      <p className="field-help">
        Rules repeat each week in {rules.data?.timezone ?? identity.timezone}. A
        preference can be relaxed; “never” is a firm restriction.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label>
          Day of week
          <select
            value={weekday}
            onChange={(event) => setWeekday(Number(event.target.value))}
          >
            {days.map((day, i) => (
              <option value={i} key={day}>
                {day}
              </option>
            ))}
          </select>
        </label>
        <label>
          Rule strength
          <select
            value={kind}
            onChange={(event) =>
              setKind(event.target.value as keyof typeof strengths)
            }
          >
            {Object.entries(strengths).map(([key, label]) => (
              <option value={key} key={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <button disabled={saving || !rules.data}>Add weekly rule</button>
      </form>
      {rules.isError && (
        <p role="alert">
          Weekly preferences could not be loaded.{" "}
          <button onClick={() => void rules.refetch()}>Retry</button>
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <ul>
        {rules.data?.items?.map((rule) => (
          <li key={rule.id}>
            {days[rule.weekday]}: {strengths[rule.kind]}{" "}
            <button
              className="secondary"
              disabled={saving}
              onClick={() => void save(rule.id)}
              aria-label={`Remove ${days[rule.weekday]} rule`}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}
