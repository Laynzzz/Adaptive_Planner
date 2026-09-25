import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import ProgressPanel from "./ProgressPanel";

afterEach(() => vi.unstubAllGlobals());
test("missed work records zero observed time and requires the user's remaining estimate", async () => {
  let saved: Record<string, unknown> | undefined;
  vi.stubGlobal("fetch", async (_url: string, options: RequestInit) => {
    if (options.method === "POST") saved = JSON.parse(options.body as string);
    return new Response(JSON.stringify({ items: [] }));
  });
  render(<QueryClientProvider client={new QueryClient()}><ProgressPanel
    identity={{ id: "u1", name: "Demo", timezone: "UTC", csrf_token: "test", revision: 5, capabilities: [] }}
    tasks={[{ id: "t1", owner_id: "u1", revision: 5, predecessor_ids: [], required_slots: 8,
      title: "Study", remaining_minutes: 120, priority: 3, state: "TODO",
      deadline: null, release_at: null, splittable: true, min_block_slots: 2, max_block_slots: 12,
      short_final_allowed: false, created_at: "2026-09-25T00:00:00Z" }]}
    onChanged={vi.fn()} /></QueryClientProvider>);
  await userEvent.selectOptions(screen.getByLabelText("Task to update"), "t1");
  expect(screen.getByLabelText("New remaining estimate (minutes)")).toHaveValue(null);
  await userEvent.type(screen.getByLabelText("New remaining estimate (minutes)"), "120");
  await userEvent.click(screen.getByRole("button", { name: "Save progress" }));
  expect(await screen.findByText("Progress recorded")).toBeInTheDocument();
  expect(saved).toEqual({ observed_minutes: 0, new_remaining_minutes: 120, complete: false, expected_revision: 5 });
});
