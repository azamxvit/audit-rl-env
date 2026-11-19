import type { EpisodeInfo, ResetObservation, Review, StepResponse } from "./types";

export class ApiError extends Error {
  constructor(public status: number, public code: string) { super(code); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, (body as { error?: string }).error ?? "http_error");
  return body as T;
}

export const api = {
  episodes: () => call<EpisodeInfo[]>("/api/episodes"),
  reset: (episode: string) =>
    call<{ session: string; observation: ResetObservation }>("/api/reset", {
      method: "POST", body: JSON.stringify({ episode }) }),
  step: (session: string, action: unknown) =>
    call<StepResponse>("/api/step", { method: "POST", body: JSON.stringify({ session, action }) }),
  review: (session: string) => call<Review>(`/api/review?session=${encodeURIComponent(session)}`),
};
