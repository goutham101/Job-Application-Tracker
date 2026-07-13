async function request(path, options = {}) {
  const res = await fetch(path, {
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
