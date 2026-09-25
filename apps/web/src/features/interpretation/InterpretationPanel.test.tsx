import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import InterpretationPanel from "./InterpretationPanel";

afterEach(() => vi.unstubAllGlobals());
const identity = { id: "u1", name: "Demo", timezone: "UTC", revision: 2,
  csrf_token: "test", capabilities: [] };
const field = (value: unknown, label = "explicit") => ({ value, label,
  requires_confirmation: label !== "explicit",
  evidence: label === "explicit" ? [{ start: 0, end: 6, text: "Review" }] : [] });
function mount() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <InterpretationPanel identity={identity} onChanged={vi.fn()} />
  </QueryClientProvider>);
}
test("interpretation only adds tasks after explicit review, resolving unknown duration", async () => {
  const writes: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", async (url: string, options: RequestInit) => {
    if (options.method === "POST") {
      writes.push({ url, body: JSON.parse(options.body as string) });
      return new Response(JSON.stringify({ id: "i1", state: "QUEUED", planning_revision: 2 }));
    }
    return new Response(JSON.stringify({ id: "i1", state: "READY", planning_revision: 2,
      source_text: "Review chapter", timezone: "UTC", reference_now: "2026-09-25T12:00:00Z",
      proposal: { constraints: [], tasks: [{ key: "task_1", title: field("Review chapter"),
        remaining_minutes: field(null, "unknown"), deadline: field(null, "unknown"),
        priority: field(3, "inferred"), predecessor_keys: [] }], unresolved_fields: [] } }));
  });
  mount();
  await userEvent.type(screen.getByLabelText("Describe your tasks"), "Review chapter");
  await userEvent.click(screen.getByRole("button", { name: "Extract draft" }));
  const review = await screen.findByRole("group", { name: "Review task 1" });
  expect(writes).toHaveLength(1);
  expect(screen.getByRole("button", { name: "Add reviewed tasks" })).toBeDisabled();
  await userEvent.type(within(review).getByLabelText("Remaining minutes"), "60");
  await userEvent.click(within(review).getByLabelText("Use no deadline"));
  await userEvent.click(within(review).getByLabelText("Confirm Priority"));
  await userEvent.click(screen.getByRole("button", { name: "Add reviewed tasks" }));
  expect(writes).toHaveLength(2);
  expect(writes[1].body).toMatchObject({ expected_revision: 2, selected_task_keys: ["task_1"],
    confirmed_fields: ["tasks.task_1.priority"],
    overrides: { "tasks.task_1.remaining_minutes": 60, "tasks.task_1.deadline": null } });
});
test("provider failure leaves source text and manual entry available", async () => {
  vi.stubGlobal("fetch", async () => new Response(JSON.stringify({ error: {
    code: "PROVIDER_TIMEOUT", message: "Extraction timed out." } }), { status: 503 }));
  mount();
  await userEvent.type(screen.getByLabelText("Describe your tasks"), "My unfinished draft");
  await userEvent.click(screen.getByRole("button", { name: "Extract draft" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Extraction timed out.");
  expect(screen.getByLabelText("Describe your tasks")).toHaveValue("My unfinished draft");
  expect(screen.getByRole("link", { name: "Use the task form" })).toHaveAttribute("href", "#manual-task-form");
});
