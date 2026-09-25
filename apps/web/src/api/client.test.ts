import { afterEach, expect, test, vi } from "vitest";
import { mutate } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

test("brief command contention retries the identical body and idempotency key", async () => {
  vi.useFakeTimers();
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ error: { code: "COMMAND_IN_PROGRESS" } }), {
        status: 409,
      }),
    )
    .mockResolvedValueOnce(new Response(JSON.stringify({ revision: 5 })));
  vi.stubGlobal("fetch", fetch);
  const saving = mutate(
    "/tasks/t",
    "PATCH",
    { expected_revision: 4 },
    "csrf",
    "same-key",
  );
  await vi.runAllTimersAsync();
  await expect(saving).resolves.toEqual({ revision: 5 });
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[0][1].body).toBe(fetch.mock.calls[1][1].body);
  expect(fetch.mock.calls[1][1].headers["Idempotency-Key"]).toBe("same-key");
});

test("revision conflicts are never silently retried", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "REVISION_CONFLICT" } }), {
        status: 409,
      }),
    );
  vi.stubGlobal("fetch", fetch);
  await expect(
    mutate("/tasks/t", "PATCH", {}, "csrf", "key"),
  ).rejects.toMatchObject({ code: "REVISION_CONFLICT" });
  expect(fetch).toHaveBeenCalledTimes(1);
});

test("persistent contention stops after three attempts", async () => {
  vi.useFakeTimers();
  const fetch = vi
    .fn()
    .mockImplementation(
      async () =>
        new Response(
          JSON.stringify({ error: { code: "COMMAND_IN_PROGRESS" } }),
          { status: 409 },
        ),
    );
  vi.stubGlobal("fetch", fetch);
  const checked = expect(
    mutate("/tasks/t", "PATCH", {}, "csrf", "key"),
  ).rejects.toMatchObject({ code: "COMMAND_IN_PROGRESS" });
  await vi.runAllTimersAsync();
  await checked;
  expect(fetch).toHaveBeenCalledTimes(3);
});
