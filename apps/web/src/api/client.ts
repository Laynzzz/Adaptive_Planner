import type { components } from "./generated";
export type Identity = components["schemas"]["MeResponse"];
export type Task = components["schemas"]["TaskResponse"];
export type TaskPage = components["schemas"]["TaskPage"];
export type Availability = components["schemas"]["AvailabilityResponse"];
export function showInstant(
  instant: components["schemas"]["Interval"]["start"],
): string {
  return typeof instant === "string"
    ? instant.replace("T", " ")
    : `${instant.local.replace("T", " ")} ${instant.timezone ?? "UTC"}`;
}
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    credentials: "same-origin",
    ...options,
    signal: options.signal ?? AbortSignal.timeout(15000),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = data.error ?? data.detail ?? data;
    throw new ApiError(
      response.status,
      error.code ?? "REQUEST_FAILED",
      typeof error.message === "string"
        ? error.message
        : `Request failed (${response.status}). Please try again.`,
    );
  }
  return data as T;
}
export async function mutate<T>(
  path: string,
  method: string,
  body: unknown,
  csrf: string,
  key: string,
): Promise<T> {
  const options = {
    method,
    body: JSON.stringify(body),
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf,
      "Idempotency-Key": key,
    },
  };
  for (let attempt = 0; ; attempt++) {
    try {
      return await request<T>(path, options);
    } catch (error) {
      if (
        !(error instanceof ApiError) ||
        error.status !== 409 ||
        error.code !== "COMMAND_IN_PROGRESS" ||
        attempt >= 2
      )
        throw error;
      await new Promise((resolve) => setTimeout(resolve, 75 * (attempt + 1)));
    }
  }
}
