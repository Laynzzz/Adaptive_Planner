import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import ActivePlan from "./ActivePlan";

afterEach(() => vi.unstubAllGlobals());
test("selected block controls use saved protected inputs after reload", async () => {
  let command: Record<string, unknown> | undefined;
  vi.stubGlobal("fetch", async (url: string, options: RequestInit) => {
    if (options.method === "POST") { command = JSON.parse(options.body as string); return new Response("{}"); }
    if (url.endsWith("/active-plan")) return new Response(JSON.stringify({ id: "p1",
      candidate: { blocks: [{ id: "b1", task_id: "t1", start: "2030-10-01T09:00:00Z",
        end: "2030-10-01T10:00:00Z", locked: false }] } }));
    return new Response(JSON.stringify({ items: [{ id: "b1", locked: true, active: true, source: "LOCKED",
      start: "2030-10-01T09:00:00Z", end: "2030-10-01T10:00:00Z" }], revision: 4 }));
  });
  render(<QueryClientProvider client={new QueryClient()}><ActivePlan
    identity={{ id: "u1", name: "Demo", timezone: "UTC", csrf_token: "test", revision: 4, capabilities: [] }}
    taskNames={{ t1: "Study" }} onChanged={vi.fn()} /></QueryClientProvider>);
  await userEvent.click(await screen.findByRole("button", { name: "Unlock this block" }));
  expect(command).toEqual({ locked: false, expected_revision: 4 });
  expect(await screen.findByText(/Block unlocked/)).toBeInTheDocument();
});
