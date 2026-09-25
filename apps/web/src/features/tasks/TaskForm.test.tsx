import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import TaskForm from "./TaskForm";

const identity = {
  id: "test-owner",
  name: "Demo",
  timezone: "UTC",
  revision: 7,
  csrf_token: "synthetic-csrf",
  capabilities: [],
};
afterEach(() => vi.unstubAllGlobals());

test("submits reviewed task fields with revision and CSRF to the API", async () => {
  let sent: { url: string; options: RequestInit } | undefined;
  vi.stubGlobal("fetch", async (url: string, options: RequestInit) => {
    sent = { url, options };
    return new Response(JSON.stringify({ id: "task-1", revision: 8 }), {
      status: 201,
    });
  });
  const saved = vi.fn();
  render(<TaskForm identity={identity} onSaved={saved} />);
  await userEvent.type(screen.getByLabelText("Task name"), "Write lab report");
  await userEvent.clear(screen.getByLabelText("Remaining minutes"));
  await userEvent.type(screen.getByLabelText("Remaining minutes"), "90");
  await userEvent.click(screen.getByRole("button", { name: "Add task" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Task added");
  expect(sent?.url).toBe("/api/v1/tasks");
  expect(JSON.parse(sent!.options.body as string)).toMatchObject({
    title: "Write lab report",
    remaining_minutes: 90,
    expected_revision: 7,
  });
  expect(sent?.options.headers).toMatchObject({
    "X-CSRF-Token": "synthetic-csrf",
  });
  expect(saved).toHaveBeenCalledOnce();
});

test("retains task input after a conflict and uses the same command key for an unchanged retry", async () => {
  const keys: string[] = [];
  vi.stubGlobal("fetch", async (_url: string, options: RequestInit) => {
    keys.push((options.headers as Record<string, string>)["Idempotency-Key"]);
    return new Response(
      JSON.stringify({
        code: "STALE_REVISION",
        message: "The plan changed. Refresh before saving.",
      }),
      { status: 409 },
    );
  });
  render(<TaskForm identity={identity} onSaved={() => {}} />);
  await userEvent.type(screen.getByLabelText("Task name"), "Keep my draft");
  await userEvent.click(screen.getByRole("button", { name: "Add task" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The plan changed",
  );
  expect(screen.getByLabelText("Task name")).toHaveValue("Keep my draft");
  await userEvent.click(screen.getByRole("button", { name: "Add task" }));
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
});
