import { useRef, useState } from "react";
import { ApiError, mutate, request, type Identity } from "../../api/client";
import type { components } from "../../api/generated";

export default function TimezoneSettings({
  identity,
  onChanged,
}: {
  identity: Identity;
  onChanged: () => void;
}) {
  const [timezone, setTimezone] = useState(identity.timezone);
  const [preview, setPreview] = useState<
    components["schemas"]["TimezonePreview"] | null
  >(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const pending = useRef({ body: "", key: "" });
  return (
    <details className="interpretation-panel">
      <summary>Timezone settings</summary>
      <p className="field-help">
        Current timezone: {identity.timezone}. Existing events, timestamp
        deadlines and available windows keep their actual times. Date-only
        deadlines keep their calendar dates; weekly rules follow the new
        timezone.
      </p>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setError("");
          setNotice("");
          setPreview(null);
          setConfirmed(false);
          try {
            setPreview(
              await request(
                `/settings/timezone-preview?timezone=${encodeURIComponent(timezone)}`,
              ),
            );
          } catch (failure) {
            setError(
              failure instanceof Error
                ? failure.message
                : "Timezone preview failed.",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Planning timezone
          <input
            value={timezone}
            list="planning-timezones"
            maxLength={100}
            disabled={busy}
            required
            onChange={(event) => {
              setTimezone(event.target.value);
              setPreview(null);
              setConfirmed(false);
            }}
          />
        </label>
        <datalist id="planning-timezones">
          {[
            "UTC",
            "America/New_York",
            "America/Los_Angeles",
            "Europe/London",
            "Asia/Shanghai",
            "Asia/Tokyo",
            "Australia/Sydney",
          ].map((zone) => (
            <option value={zone} key={zone} />
          ))}
        </datalist>
        <button disabled={busy || timezone === identity.timezone}>
          Preview timezone change
        </button>
      </form>
      {preview && (
        <div className="timezone-preview">
          <h3>
            {preview.old_timezone} → {preview.timezone}
          </h3>
          <p>
            {preview.preserved_fixed_events} fixed events and{" "}
            {preview.preserved_available_windows} available windows preserve
            their actual times.
          </p>
          {preview.date_deadlines.length > 0 ? (
            <ul>
              {preview.date_deadlines.map((deadline) => (
                <li key={deadline.task_id}>
                  <strong>{deadline.title}</strong> stays due on {deadline.date}
                  . Its exclusive UTC deadline changes from {deadline.old_bound}{" "}
                  to {deadline.new_bound}.
                </li>
              ))}
            </ul>
          ) : (
            <p>No date-only deadlines will change.</p>
          )}
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            I reviewed these timezone changes
          </label>
          <button
            disabled={busy || !confirmed}
            onClick={async () => {
              const body = {
                timezone: preview.timezone,
                expected_revision: preview.revision,
                preview_hash: preview.preview_hash,
                confirmed: true,
              };
              const serialized = JSON.stringify(body);
              if (pending.current.body !== serialized)
                pending.current = {
                  body: serialized,
                  key: crypto.randomUUID(),
                };
              setBusy(true);
              setError("");
              try {
                await mutate(
                  "/settings/timezone",
                  "PUT",
                  body,
                  identity.csrf_token,
                  pending.current.key,
                );
                setNotice(
                  "Timezone updated. Review the next plan before activating it.",
                );
                setPreview(null);
                setConfirmed(false);
                pending.current = { body: "", key: "" };
                onChanged();
              } catch (failure) {
                setError(
                  failure instanceof Error
                    ? failure.message
                    : "Timezone change failed.",
                );
                if (failure instanceof ApiError && failure.status === 409) {
                  setPreview(null);
                  setConfirmed(false);
                  onChanged();
                }
              } finally {
                setBusy(false);
              }
            }}
          >
            Apply timezone change
          </button>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </details>
  );
}
