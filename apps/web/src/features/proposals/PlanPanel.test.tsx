import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import PlanPanel from "./PlanPanel";

const identity = {
  id: "owner",
  name: "Demo",
  timezone: "UTC",
  revision: 4,
  csrf_token: "test",
  capabilities: [],
};
const proposal = {
  id: "p1",
  state: "CURRENT",
  planning_revision: 4,
  publication_state: "NOT_REQUESTED",
  activated_at: null,
  candidate: {
    status: "FEASIBLE",
    source_policy: "GREEDY",
    blocks: [
      {
        id: "b1",
        task_id: "t1",
        start: "2026-10-01T09:00:00Z",
        end: "2026-10-01T10:00:00Z",
        locked: false,
      },
    ],
    constraint_report: [],
    score: { quality: 0.95 },
    solver_metadata: {},
  },
};
afterEach(() => vi.unstubAllGlobals());
function mount() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <PlanPanel identity={identity} onChanged={() => {}} />
    </QueryClientProvider>,
  );
}
test("proposal stays inactive until the user explicitly activates it", async () => {
  const writes: string[] = [];
  vi.stubGlobal("fetch", async (url: string, options: RequestInit) => {
    if (options.method === "POST") {
      writes.push(url);
      return new Response(
        JSON.stringify({
          ...proposal,
          state: "ACTIVE",
          activated_at: "2026-09-25T12:00:00Z",
        }),
      );
    }
    return new Response(JSON.stringify({ items: [proposal] }));
  });
  mount();
  const button = await screen.findByRole("button", {
    name: "Activate this plan",
  });
  expect(writes).toHaveLength(0);
  await userEvent.click(button);
  expect(await screen.findByText("Plan activated")).toBeInTheDocument();
  expect(writes).toEqual(["/api/v1/proposals/p1/activate"]);
});
test("unknown solver outcome cannot be activated or described as infeasible", async () => {
  vi.stubGlobal(
    "fetch",
    async () =>
      new Response(
        JSON.stringify({
          items: [
            {
              ...proposal,
              candidate: {
                ...proposal.candidate,
                status: "UNKNOWN",
                blocks: [],
              },
            },
          ],
        }),
      ),
  );
  mount();
  expect(
    await screen.findByText("No conclusion within the search budget"),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Activate this plan" }),
  ).not.toBeInTheDocument();
});

test("failed scheduling shows the candidate conflict report when no proposal exists", async () => {
  vi.stubGlobal("fetch", async (url: string) => {
    if (url.endsWith("/replans"))
      return new Response(JSON.stringify({ job_id: "j1" }));
    if (url.includes("/jobs/"))
      return new Response(
        JSON.stringify({
          id: "j1",
          state: "FAILED",
          planning_revision: 4,
          reason_code: "INFEASIBLE",
          candidate: {
            ...proposal.candidate,
            status: "INFEASIBLE",
            blocks: [],
            constraint_report: [
              {
                code: "DEADLINE_CAPACITY",
                related_ids: [],
                facts: { required_slots: 12, available_slots: 4 },
              },
            ],
          },
        }),
      );
    return new Response(JSON.stringify({ items: [] }));
  });
  mount();
  await userEvent.click(
    await screen.findByRole("button", { name: "Generate plan" }),
  );
  expect(
    await screen.findByText("These constraints cannot all be met"),
  ).toBeInTheDocument();
  expect(screen.getByText("deadline capacity")).toBeInTheDocument();
  expect(screen.getByText(/"required_slots": 12/)).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Activate this plan" }),
  ).not.toBeInTheDocument();
});
