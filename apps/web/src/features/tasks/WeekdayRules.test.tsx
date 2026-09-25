import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import WeekdayRules from "./WeekdayRules";

afterEach(() => vi.unstubAllGlobals());
test("weekday rule is explicit and uses its consistent read revision", async () => {
  let command: unknown;
  vi.stubGlobal("fetch", async (_url: string, options: RequestInit) => {
    if (options.method === "POST") {
      command = JSON.parse(options.body as string);
      return new Response(JSON.stringify({ id: "r1", revision: 4 }));
    }
    return new Response(
      JSON.stringify({ items: [], timezone: "UTC", revision: 3 }),
    );
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <WeekdayRules
        identity={{
          id: "u1",
          name: "Demo",
          timezone: "UTC",
          csrf_token: "test",
          revision: 9,
          capabilities: [],
        }}
        onChanged={vi.fn()}
      />
    </QueryClientProvider>,
  );
  await userEvent.click(screen.getByText("Weekly preferences"));
  await userEvent.selectOptions(
    await screen.findByLabelText("Rule strength"),
    "HARD_UNAVAILABLE",
  );
  await userEvent.selectOptions(screen.getByLabelText("Day of week"), "6");
  await userEvent.click(
    screen.getByRole("button", { name: "Add weekly rule" }),
  );
  expect(command).toEqual({
    kind: "HARD_UNAVAILABLE",
    weekday: 6,
    expected_revision: 3,
  });
  expect(await screen.findByText("Weekly rule saved")).toBeInTheDocument();
});
