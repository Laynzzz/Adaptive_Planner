import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import Constraints from "./Constraints";
const identity = {
  id: "owner",
  name: "Demo",
  timezone: "UTC",
  revision: 5,
  csrf_token: "test",
  capabilities: [],
};
afterEach(() => vi.unstubAllGlobals());
test("adds a fixed commitment with explicit times and expected revision", async () => {
  let sent: unknown;
  vi.stubGlobal("fetch", async (_url: string, options: RequestInit) => {
    sent = JSON.parse(options.body as string);
    return new Response(JSON.stringify({ revision: 6 }));
  });
  render(<Constraints identity={identity} tasks={[]} onChanged={() => {}} />);
  await userEvent.click(
    screen.getByText("Fixed commitments and task dependencies"),
  );
  await userEvent.type(
    screen.getByLabelText("Commitment name"),
    "Chemistry class",
  );
  await userEvent.type(
    screen.getByLabelText("Busy from (UTC)"),
    "2026-10-01T10:00",
  );
  await userEvent.type(
    screen.getByLabelText("Busy until (UTC)"),
    "2026-10-01T11:00",
  );
  await userEvent.click(screen.getByRole("button", { name: "Add commitment" }));
  expect(await screen.findByText("Commitment added")).toBeInTheDocument();
  expect(sent).toEqual({
    title: "Chemistry class",
    start: "2026-10-01T10:00",
    end: "2026-10-01T11:00",
    expected_revision: 5,
  });
});
