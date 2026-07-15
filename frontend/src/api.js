// Empty by default so the Vite dev proxy (see vite.config.js) still handles
// local dev unchanged. In production, set VITE_API_URL to the deployed API's
// origin at build time — Vite bakes it into the bundle.
const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: options.body ? { "Content-Type": "application/json" } : undefined,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data?.detail;
    const err = new Error(
      typeof detail === "string" ? detail : `Request failed (${res.status})`
    );
    err.status = res.status;
    throw err;
  }
  return data;
}

export const api = {
  listApplications: () => request("/applications"),
  createApplication: (body) =>
    request("/applications", { method: "POST", body: JSON.stringify(body) }),
  deleteApplication: (id) =>
    request(`/applications/${id}`, { method: "DELETE" }),
  addEvent: (id, body, backfill = false) =>
    request(`/applications/${id}/events${backfill ? "?backfill=true" : ""}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  funnel: () => request("/stats/funnel"),
  timeInStage: () => request("/stats/time-in-stage"),
  bySource: () => request("/stats/by-source"),
  byStage: () => request("/stats/by-stage"),
};
