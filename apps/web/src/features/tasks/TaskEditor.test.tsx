import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import type { Identity, Task } from "../../api/client";
import TaskEditor from "./TaskEditor";

const identity: Identity = {
  id: "owner",
  name: "Demo",
  timezone: "UTC",
  revision: 99,
  csrf_token: "csrf",
  capabilities: [],
};
const task: Task = {
  id: "task-1",
  owner_id: "owner",
  title: "Draft report",
  remaining_minutes: 60,
  priority: 3,
  state: "TODO",
  revision: 7,
  required_slots: 4,
  created_at: "2026-09-25T00:00:00Z",
  predecessor_ids: [],
  deadline: {
    kind: "TIMESTAMP",
    value: "2026-09-30T18:00:00Z",
    timezone: "UTC",
  },
  splittable: true,
  min_block_slots: 2,
  max_block_slots: 12,
  short_final_allowed: false,
};
afterEach(() => vi.unstubAllGlobals());

test("edits coherent task revision and preserves an unchanged exact deadline", async () => {
  const requests: { path: string; options: RequestInit }[] = [];
  vi.stubGlobal("fetch", async (path: string, options: RequestInit) => {
    requests.push({ path, options });
    return new Response(JSON.stringify({ revision: 8 }));
  });
  const changed = vi.fn();
  render(<TaskEditor identity={identity} task={task} onChanged={changed} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Edit task Draft report" }),
  );
  await userEvent.clear(screen.getByLabelText("Task title"));
  await userEvent.type(screen.getByLabelText("Task title"), "Revised report");
  await userEvent.click(
    screen.getByRole("button", { name: "Save task changes" }),
  );
  expect(changed).toHaveBeenCalledOnce();
  expect(requests[0].path).toBe("/api/v1/tasks/task-1");
  expect(requests[0].options.method).toBe("PATCH");
  expect(JSON.parse(requests[0].options.body as string)).toMatchObject({
    title: "Revised report",
    expected_revision: 7,
    deadline: task.deadline,
  });
});

test("keeps the draft and idempotency key after a conflict", async () => {
  const keys: string[] = [];
  vi.stubGlobal("fetch", async (_path: string, options: RequestInit) => {
    keys.push((options.headers as Record<string, string>)["Idempotency-Key"]);
    return new Response(
      JSON.stringify({ code: "STALE_REVISION", message: "The plan changed." }),
      { status: 409 },
    );
  });
  render(<TaskEditor identity={identity} task={task} onChanged={() => {}} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Edit task Draft report" }),
  );
  await userEvent.clear(screen.getByLabelText("Task title"));
  await userEvent.type(screen.getByLabelText("Task title"), "Retained edit");
  await userEvent.click(
    screen.getByRole("button", { name: "Save task changes" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The plan changed.",
  );
  expect(screen.getByLabelText("Task title")).toHaveValue("Retained edit");
  await userEvent.click(
    screen.getByRole("button", { name: "Save task changes" }),
  );
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
});

test("cancellation requires an explicit checkbox and uses task revision", async () => {
  const fetch = vi.fn(
    async () => new Response(JSON.stringify({ revision: 8 })),
  );
  vi.stubGlobal("fetch", fetch);
  render(<TaskEditor identity={identity} task={task} onChanged={() => {}} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Edit task Draft report" }),
  );
  expect(screen.getByRole("button", { name: "Cancel task" })).toBeDisabled();
  expect(fetch).not.toHaveBeenCalled();
  await userEvent.click(screen.getByLabelText("I want to cancel this task"));
  await userEvent.click(screen.getByRole("button", { name: "Cancel task" }));
  expect(fetch).toHaveBeenCalledOnce();
  const [url, options] = fetch.mock.calls[0] as unknown as [
    string,
    RequestInit,
  ];
  expect(url).toBe("/api/v1/tasks/task-1/cancel");
  expect(JSON.parse(options.body as string)).toEqual({ expected_revision: 7 });
});
