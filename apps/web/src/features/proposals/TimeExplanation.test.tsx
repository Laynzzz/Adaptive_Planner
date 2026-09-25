import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import TimeExplanation from "./TimeExplanation";

afterEach(() => vi.unstubAllGlobals());
test("time explanation retains original values and shows inward rounding", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            timezone: "UTC",
            original_time_inputs: [
              {
                field: "availability.0.start",
                value: "2026-09-25T09:07",
                timezone: "UTC",
              },
            ],
            rounding_losses: [
              {
                field: "availability.0.start",
                original: "2026-09-25T09:07:00Z",
                rounded: "2026-09-25T09:15:00Z",
                seconds: 480,
              },
            ],
          }),
        ),
      ),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TimeExplanation path="/proposals/p1/time-inputs" taskNames={{}} />
    </QueryClientProvider>,
  );
  await userEvent.click(
    screen.getByText("Original times and planning adjustments"),
  );
  expect(await screen.findByText("2026-09-25T09:07:00Z")).toBeInTheDocument();
  expect(screen.getByText("2026-09-25T09:15:00Z")).toBeInTheDocument();
  expect(screen.getByText("8 minutes")).toBeInTheDocument();
});
