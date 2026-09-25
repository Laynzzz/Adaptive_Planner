import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import TimezoneSettings from "./TimezoneSettings";

afterEach(() => vi.unstubAllGlobals());
test("timezone changes require an explicit preview and confirmation", async () => {
  let command: unknown;
  vi.stubGlobal("fetch", async (_url: string, options: RequestInit) => {
    if (options.method === "PUT") {
      command = JSON.parse(options.body as string);
      return new Response(
        JSON.stringify({ revision: 5, timezone: "America/New_York" }),
      );
    }
    return new Response(
      JSON.stringify({
        old_timezone: "UTC",
        timezone: "America/New_York",
        revision: 4,
        date_deadlines: [],
        preserved_fixed_events: 2,
        preserved_available_windows: 1,
        preview_hash: "a".repeat(64),
      }),
    );
  });
  render(
    <TimezoneSettings
      identity={{
        id: "u1",
        name: "Demo",
        timezone: "UTC",
        csrf_token: "test",
        revision: 3,
        capabilities: [],
      }}
      onChanged={vi.fn()}
    />,
  );
  await userEvent.click(screen.getByText("Timezone settings"));
  await userEvent.clear(screen.getByLabelText("Planning timezone"));
  await userEvent.type(
    screen.getByLabelText("Planning timezone"),
    "America/New_York",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Preview timezone change" }),
  );
  const apply = await screen.findByRole("button", {
    name: "Apply timezone change",
  });
  expect(apply).toBeDisabled();
  await userEvent.click(
    screen.getByLabelText("I reviewed these timezone changes"),
  );
  await userEvent.click(apply);
  expect(command).toEqual({
    timezone: "America/New_York",
    expected_revision: 4,
    preview_hash: "a".repeat(64),
    confirmed: true,
  });
  expect(
    await screen.findByText(
      "Timezone updated. Review the next plan before activating it.",
    ),
  ).toBeInTheDocument();
});
