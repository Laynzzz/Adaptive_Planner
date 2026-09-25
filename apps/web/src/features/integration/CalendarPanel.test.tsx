import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import CalendarPanel from "./CalendarPanel";

afterEach(() => vi.unstubAllGlobals());
test("calendar simulator connection is explicit and uses the read calendar revision", async () => {
  let command: Record<string, unknown> | undefined;
  vi.stubGlobal("fetch", async (_url: string, options: RequestInit) => {
    if (options.method === "POST") { command = JSON.parse(options.body as string); return new Response(JSON.stringify({ state: "CONNECTED", revision: 4 })); }
    return new Response(JSON.stringify({ state: "DISCONNECTED", revision: 3, live_configured: false,
      mock_available: true, conflicts: [], published_count: 0, pending_count: 0 }));
  });
  render(<QueryClientProvider client={new QueryClient()}><CalendarPanel
    identity={{ id: "u1", name: "Demo", timezone: "UTC", csrf_token: "test", revision: 4, capabilities: [] }}
    onChanged={vi.fn()} /></QueryClientProvider>);
  const connect = await screen.findByRole("button", { name: "Connect calendar" });
  expect(connect).toBeDisabled();
  await userEvent.click(screen.getByLabelText("This is a dedicated calendar for synthetic tasks"));
  await userEvent.click(connect);
  expect(command).toEqual({ provider: "MOCK", calendar_id: "adaptive-planner-demo",
    dedicated_synthetic_confirmed: true, expected_revision: 3 });
  expect(await screen.findByText("Calendar connection saved")).toBeInTheDocument();
});
