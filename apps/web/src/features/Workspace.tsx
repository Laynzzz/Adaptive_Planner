import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useRef, useState } from "react";
import {
  ApiError,
  mutate,
  request,
  showInstant,
  type Availability,
  type Identity,
  type TaskPage,
} from "../api/client";
import TaskForm from "./tasks/TaskForm";
import PlanPanel from "./proposals/PlanPanel";
import Constraints from "./tasks/Constraints";
import InterpretationPanel from "./interpretation/InterpretationPanel";
import ProgressPanel from "./progress/ProgressPanel";
import WhatIfPanel from "./comparison/WhatIfPanel";
import ActivePlan from "./progress/ActivePlan";
import CalendarPanel from "./integration/CalendarPanel";
import WeekdayRules from "./tasks/WeekdayRules";
import TimezoneSettings from "./settings/TimezoneSettings";
import Commitments from "./tasks/Commitments";
import TaskEditor from "./tasks/TaskEditor";

export default function Workspace() {
  const cache = useQueryClient();
  const identity = useQuery({
    queryKey: ["me"],
    queryFn: () => request<Identity>("/me"),
    retry: false,
  });
  const tasks = useInfiniteQuery({
    queryKey: ["tasks", identity.data?.id],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      request<TaskPage>(
        `/tasks${pageParam ? "?cursor=" + encodeURIComponent(pageParam) : ""}`,
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: !!identity.data?.id,
  });
  const allTasks = tasks.data?.pages.flatMap((page) => page.items) ?? [];
  const availability = useQuery({
    queryKey: ["availability", identity.data?.id],
    queryFn: () => request<Availability>("/availability"),
    enabled: !!identity.data?.id,
  });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const windowCommand = useRef({ body: "", key: "" });
  const refresh = () => {
    void cache.invalidateQueries({ queryKey: ["me"] });
    void cache.invalidateQueries({ queryKey: ["tasks"] });
    void cache.invalidateQueries({ queryKey: ["availability"] });
    void cache.invalidateQueries({ queryKey: ["proposals"] });
    void cache.invalidateQueries({ queryKey: ["job"] });
    void cache.invalidateQueries({ queryKey: ["protected-work"] });
    void cache.invalidateQueries({ queryKey: ["work-logs"] });
    void cache.invalidateQueries({ queryKey: ["active-plan"] });
    void cache.invalidateQueries({ queryKey: ["calendar"] });
    void cache.invalidateQueries({ queryKey: ["weekday-rules"] });
    void cache.invalidateQueries({ queryKey: ["fixed-events"] });
  };
  if (identity.isPending)
    return (
      <p role="status" className="empty-agenda">
        Loading your workspace…
      </p>
    );
  if (identity.error instanceof ApiError && identity.error.status === 401)
    return (
      <div className="empty-agenda">
        <h3>A plan that belongs to you</h3>
        <p>Sign in to add tasks and set the hours you have available.</p>
        <a className="button-link" href="/api/v1/auth/login">
          Sign in
        </a>
      </div>
    );
  if (!identity.data?.id)
    return (
      <div className="empty-agenda">
        <p role="alert">Your workspace could not be loaded.</p>
        <button onClick={() => void identity.refetch()}>
          Reload workspace
        </button>
      </div>
    );
  const me = identity.data;
  return (
    <>
      <div className="account-bar">
        <span>
          {me.name} <span className="subtle">/ {me.timezone}</span>
        </span>
        <div className="button-group">
          <button className="secondary" onClick={refresh}>
            Refresh
          </button>
          <button
            className="secondary"
            onClick={async () => {
              try {
                await mutate(
                  "/auth/logout",
                  "POST",
                  {},
                  me.csrf_token,
                  crypto.randomUUID(),
                );
                cache.clear();
                window.location.assign("/");
              } catch (failure) {
                setError(
                  failure instanceof Error
                    ? failure.message
                    : "Sign out failed.",
                );
              }
            }}
          >
            Sign out
          </button>
        </div>
      </div>
      {error && (
        <p role="alert" className="inline-error">
          {error}
        </p>
      )}
      <div className="workspace-columns">
        <div>
          <div id="manual-task-form">
            <TaskForm identity={me} onSaved={refresh} />
          </div>
          <InterpretationPanel identity={me} onChanged={refresh} />
          <WeekdayRules identity={me} onChanged={refresh} />
          <form
            className="availability-form"
            aria-label="Available time"
            onSubmit={async (event) => {
              event.preventDefault();
              const form = event.currentTarget;
              const fields = new FormData(form);
              const start = fields.get("start") as string;
              const end = fields.get("end") as string;
              if (end <= start) {
                setError("Available time must end after it starts.");
                return;
              }
              const body = {
                windows: [
                  ...(availability.data?.windows ?? []),
                  { start, end },
                ],
                expected_revision: availability.data!.revision,
              };
              const serialized = JSON.stringify(body);
              if (windowCommand.current.body !== serialized)
                windowCommand.current = {
                  body: serialized,
                  key: crypto.randomUUID(),
                };
              setSaving(true);
              setError("");
              setNotice("");
              try {
                await mutate(
                  "/availability",
                  "PUT",
                  body,
                  me.csrf_token,
                  windowCommand.current.key,
                );
                form.reset();
                windowCommand.current = { body: "", key: "" };
                setNotice("Available time saved");
                refresh();
              } catch (failure) {
                setError(
                  failure instanceof Error
                    ? failure.message
                    : "Available time could not be saved.",
                );
                if (failure instanceof ApiError && failure.status === 409) {
                  void availability.refetch();
                  void identity.refetch();
                }
              } finally {
                setSaving(false);
              }
            }}
          >
            <h2>Available time</h2>
            <p className="field-help">
              Enter times in {me.timezone}. Only these windows can be used for
              work.
            </p>
            <label>
              Available from ({me.timezone})
              <input name="start" type="datetime-local" step="60" required />
            </label>
            <label>
              Available until ({me.timezone})
              <input name="end" type="datetime-local" step="60" required />
            </label>
            <button type="submit" disabled={saving || !availability.data}>
              {saving ? "Saving…" : "Add available time"}
            </button>
            {notice && (
              <p className="inline-success" role="status">
                {notice}
              </p>
            )}
            {availability.isError && (
              <p role="alert">
                Available hours could not be loaded. Refresh to try again.
              </p>
            )}
            <ul className="window-list">
              {availability.data?.windows.map((window, index) => (
                <li key={index}>
                  {showInstant(window.start)} → {showInstant(window.end)}
                  <button
                    type="button"
                    className="secondary"
                    disabled={saving}
                    aria-label={`Remove available window ${index + 1}`}
                    onClick={async () => {
                      if (!availability.data) return;
                      const body = {
                        windows: availability.data.windows.filter(
                          (_, i) => i !== index,
                        ),
                        expected_revision: availability.data.revision,
                      };
                      const serialized = JSON.stringify(body);
                      if (windowCommand.current.body !== serialized)
                        windowCommand.current = {
                          body: serialized,
                          key: crypto.randomUUID(),
                        };
                      setSaving(true);
                      setError("");
                      setNotice("");
                      try {
                        await mutate(
                          "/availability",
                          "PUT",
                          body,
                          me.csrf_token,
                          windowCommand.current.key,
                        );
                        windowCommand.current = { body: "", key: "" };
                        setNotice("Available time removed");
                        refresh();
                      } catch (failure) {
                        setError(
                          failure instanceof Error
                            ? failure.message
                            : "Available time could not be removed.",
                        );
                        if (
                          failure instanceof ApiError &&
                          failure.status === 409
                        ) {
                          void availability.refetch();
                          void identity.refetch();
                        }
                      } finally {
                        setSaving(false);
                      }
                    }}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          </form>
        </div>
        <section className="task-list" aria-labelledby="task-list-title">
          <h2 id="task-list-title">Your tasks</h2>
          {tasks.isPending && <p role="status">Loading tasks…</p>}
          {tasks.isError && (
            <p role="alert">
              Tasks could not be loaded. Your draft is still here. Refresh to
              try again.
            </p>
          )}
          {tasks.isSuccess && allTasks.length === 0 && (
            <p className="field-help">
              Add your first task, then set aside time to work on it.
            </p>
          )}
          <ul>
            {allTasks.map((task) => (
              <li key={task.id}>
                <div>
                  <strong>{task.title}</strong>
                  <p>
                    {task.remaining_minutes} minutes remaining{" "}
                    <span className="subtle">/ Priority {task.priority}</span>
                  </p>
                  <p className="subtle">
                    {task.deadline
                      ? `Due ${task.deadline.value}`
                      : "No deadline"}{" "}
                    · {task.state}
                  </p>
                  <TaskEditor identity={me} task={task} onChanged={refresh} />
                </div>
              </li>
            ))}
          </ul>
          {tasks.hasNextPage && (
            <button
              className="secondary"
              disabled={tasks.isFetchingNextPage}
              onClick={() => void tasks.fetchNextPage()}
            >
              {tasks.isFetchingNextPage ? "Loading…" : "Load more tasks"}
            </button>
          )}
          <Constraints
            identity={me}
            tasks={allTasks.filter(
              (task) => !["DONE", "CANCELLED"].includes(task.state),
            )}
            onChanged={refresh}
          />
          <Commitments identity={me} tasks={allTasks} onChanged={refresh} />
        </section>
      </div>
      <PlanPanel
        identity={me}
        onChanged={refresh}
        taskNames={Object.fromEntries(
          allTasks.map((task) => [task.id, task.title]),
        )}
      />
      <ProgressPanel identity={me} tasks={allTasks} onChanged={refresh} />
      <ActivePlan
        identity={me}
        taskNames={Object.fromEntries(
          allTasks.map((task) => [task.id, task.title]),
        )}
        onChanged={refresh}
      />
      <WhatIfPanel identity={me} tasks={allTasks} onChanged={refresh} />
      <CalendarPanel identity={me} onChanged={refresh} />
      <TimezoneSettings identity={me} onChanged={refresh} />
    </>
  );
}
