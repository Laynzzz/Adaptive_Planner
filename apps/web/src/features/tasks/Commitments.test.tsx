import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import Commitments from "./Commitments";

afterEach(() => vi.unstubAllGlobals());
test("removing busy time uses the events snapshot revision", async () => {
  let command: unknown;
  vi.stubGlobal("fetch", async (_url: string, options: RequestInit) => {
    if (options.method === "DELETE") {
      command = JSON.parse(options.body as string);
      return new Response(JSON.stringify({ revision: 5 }));
    }
    return new Response(
      JSON.stringify({
        revision: 4,
        items: [
          {
            id: "e1",
            title: "Class",
            start: "2026-09-26T09:00Z",
            end: "2026-09-26T10:00Z",
          },
        ],
      }),
    );
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Commitments
        identity={{
          id: "u1",
          name: "Demo",
          timezone: "UTC",
          csrf_token: "test",
          revision: 6,
          capabilities: [],
        }}
        tasks={[]}
        onChanged={vi.fn()}
      />
    </QueryClientProvider>,
  );
  await userEvent.click(screen.getByText("Review existing commitments"));
  await userEvent.click(
    await screen.findByRole("button", { name: "Remove commitment Class" }),
  );
  expect(command).toEqual({ expected_revision: 4 });
  expect(await screen.findByText("Commitments updated")).toBeInTheDocument();
});

test("an open commitment draft keeps its captured revision through refetch and conflict retry", async () => {
  const initial = {
    revision: 4,
    items: [
      {
        id: "e1",
        title: "Class",
        start: "2026-09-26T09:00Z",
        end: "2026-09-26T10:00Z",
      },
    ],
  };
  let current = initial;
  const writes: { body: Record<string, unknown>; key: string }[] = [];
  vi.stubGlobal("fetch", async (_url: string, options: RequestInit) => {
    if (options.method === "PATCH") {
      writes.push({
        body: JSON.parse(options.body as string),
        key: (options.headers as Record<string, string>)["Idempotency-Key"],
      });
      return new Response(
        JSON.stringify({
          code: "STALE_REVISION",
          message: "Concurrent edit: reopen to review current values.",
        }),
        { status: 409 },
      );
    }
    return new Response(JSON.stringify(current));
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <Commitments
        identity={{
          id: "u1",
          name: "Demo",
          timezone: "UTC",
          csrf_token: "test",
          revision: 99,
          capabilities: [],
        }}
        tasks={[]}
        onChanged={vi.fn()}
      />
    </QueryClientProvider>,
  );
  await userEvent.click(screen.getByText("Review existing commitments"));
  await userEvent.click(await screen.findByText("Edit Class"));
  await userEvent.clear(screen.getByLabelText("Commitment title"));
  await userEvent.type(
    screen.getByLabelText("Commitment title"),
    "My retained draft",
  );
  current = {
    revision: 5,
    items: [{ ...initial.items[0], title: "Concurrent title" }],
  };
  const { act } = await import("@testing-library/react");
  await act(async () => {
    await client.refetchQueries({ queryKey: ["fixed-events", "u1"] });
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Save commitment changes" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("Concurrent edit");
  expect(writes[0].body).toEqual({
    title: "My retained draft",
    expected_revision: 4,
  });
  expect(screen.getByLabelText("Commitment title")).toHaveValue(
    "My retained draft",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Save commitment changes" }),
  );
  expect(writes[1].body.expected_revision).toBe(4);
  expect(writes[1].key).toBe(writes[0].key);
  await userEvent.click(screen.getByText("Edit Class"));
  await userEvent.click(await screen.findByText("Edit Concurrent title"));
  expect(screen.getByLabelText("Commitment title")).toHaveValue(
    "Concurrent title",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Save commitment changes" }),
  );
  expect(writes[2].body.expected_revision).toBe(5);
});
