import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import App from "./App";

afterEach(() => vi.unstubAllGlobals());
function renderApp() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

test("shows the ready application after a successful backend readiness response", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: "ready" }))),
  );
  renderApp();
  expect(await screen.findByText("Workspace connected")).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Make room for what matters." }),
  ).toBeInTheDocument();
});

test("shows a recoverable failure and reconnects when retry succeeds", async () => {
  const request = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "not_ready" }), { status: 503 }),
    )
    .mockResolvedValue(new Response(JSON.stringify({ status: "ready" })));
  vi.stubGlobal("fetch", request);
  renderApp();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Workspace is unavailable",
  );
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  await waitFor(() =>
    expect(screen.getByText("Workspace connected")).toBeInTheDocument(),
  );
});

test("does not claim connection for an unexpected readiness response", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: "not_ready" }))),
  );
  renderApp();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Workspace is unavailable",
  );
});
