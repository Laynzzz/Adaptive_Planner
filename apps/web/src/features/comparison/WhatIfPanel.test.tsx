import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import WhatIfPanel from "./WhatIfPanel";

afterEach(() => vi.unstubAllGlobals());
test("preview stays separate until the user explicitly applies the reviewed inputs", async () => {
  const writes: string[] = [];
  vi.stubGlobal("fetch", async (url: string, options: RequestInit) => {
    if (options.method === "POST") {
      writes.push(url);
      return new Response(JSON.stringify({ id: "w1", state: "QUEUED", job_id: "j1" }));
    }
    return new Response(JSON.stringify({ id: "w1", state: "READY", base_revision: 2,
      candidate: { status: "FEASIBLE", blocks: [], constraint_report: [] },
      diff: { retained: [], moved: [], added: [], removed: [], reason_codes: [] } }));
  });
  render(<QueryClientProvider client={new QueryClient()}><WhatIfPanel tasks={[]}
    identity={{ id: "u1", name: "Demo", timezone: "UTC", csrf_token: "test", revision: 2, capabilities: [] }}
    onChanged={vi.fn()} /></QueryClientProvider>);
  await userEvent.type(screen.getByLabelText("Extra time from (UTC)"), "2026-10-01T09:00");
  await userEvent.type(screen.getByLabelText("Extra time until (UTC)"), "2026-10-01T12:00");
  await userEvent.click(screen.getByRole("button", { name: "Preview changes" }));
  const apply = await screen.findByRole("button", { name: "Apply these input changes" });
  expect(writes).toEqual(["/api/v1/what-ifs"]);
  await userEvent.click(apply);
  expect(writes).toEqual(["/api/v1/what-ifs", "/api/v1/what-ifs/w1/apply"]);
  expect(await screen.findByText(/Inputs updated. Review and activate/)).toBeInTheDocument();
});
