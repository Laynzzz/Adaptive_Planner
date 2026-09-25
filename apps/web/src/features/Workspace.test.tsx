import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import Workspace from "./Workspace";

afterEach(() => vi.unstubAllGlobals());
function mount() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <Workspace />
    </QueryClientProvider>,
  );
}
test("unauthenticated visitor can start OIDC sign-in", async () => {
  vi.stubGlobal("fetch", async () => new Response("{}", { status: 401 }));
  mount();
  expect(await screen.findByRole("link", { name: "Sign in" })).toHaveAttribute(
    "href",
    "/api/v1/auth/login",
  );
});
test("workspace Refresh loads proposals produced by background replanning", async () => {
  let proposalReads = 0;
  vi.stubGlobal("fetch", async (url: string) => {
    if (url.endsWith("/active-plan")) return new Response("null");
    if (url.endsWith("/calendar/status")) return new Response(JSON.stringify({ state: "DISCONNECTED", revision: 4, conflicts: [] }));
    if (url.endsWith("/me")) return new Response(JSON.stringify({
      id: "u1", name: "Demo A", timezone: "UTC", revision: 4,
      csrf_token: "test", capabilities: [],
    }));
    if (url.endsWith("/proposals")) proposalReads += 1;
    return new Response(JSON.stringify({ items: [], windows: [], revision: 4 }));
  });
  mount();
  await screen.findByRole("button", { name: "Generate plan" });
  await screen.findByText(/Once your tasks and available hours are ready/);
  expect(proposalReads).toBe(1);
  await userEvent.click(screen.getByRole("button", { name: "Refresh" }));
  expect(proposalReads).toBe(2);
});
test("availability replacement uses its own snapshot revision when identity is newer", async () => {
  let update: Record<string, unknown> | undefined;
  vi.stubGlobal("fetch", async (url: string, options: RequestInit) => {
    if (url.endsWith("/active-plan")) return new Response("null");
    if (url.endsWith("/calendar/status")) return new Response(JSON.stringify({ state: "DISCONNECTED", revision: 4, conflicts: [] }));
    if (url.endsWith("/me"))
      return new Response(
        JSON.stringify({
          id: "u1",
          name: "Demo A",
          timezone: "UTC",
          revision: 4,
          csrf_token: "test",
          capabilities: [],
        }),
      );
    if (url.includes("/tasks"))
      return new Response(
        JSON.stringify({
          items: [
            {
              id: "t1",
              title: "Prepare exam",
              state: "TODO",
              remaining_minutes: 120,
              deadline: null,
              priority: 3,
            },
          ],
          revision: 3,
          next_cursor: null,
        }),
      );
    if (url.endsWith("/availability")) {
      if (options.method === "PUT") update = JSON.parse(options.body as string);
      return new Response(
        JSON.stringify({ windows: [], timezone: "UTC", revision: 3 }),
      );
    }
    return new Response(JSON.stringify({ items: [], revision: 3 }));
  });
  mount();
  expect(await screen.findByText("Prepare exam", { selector: "strong" })).toBeInTheDocument();
  await userEvent.type(
    screen.getByLabelText("Available from (UTC)"),
    "2026-10-01T09:00",
  );
  await userEvent.type(
    screen.getByLabelText("Available until (UTC)"),
    "2026-10-01T17:00",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Add available time" }),
  );
  expect(await screen.findByText("Available time saved")).toBeInTheDocument();
  expect(update).toEqual({
    windows: [{ start: "2026-10-01T09:00", end: "2026-10-01T17:00" }],
    expected_revision: 3,
  });
});
