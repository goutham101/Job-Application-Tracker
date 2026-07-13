import { useMemo, useState } from "react";
import {
  ArrowClockwise,
  Briefcase,
  MagnifyingGlass,
  Plus,
  TrendUp,
  Trash,
  WarningCircle,
} from "@phosphor-icons/react";
import { api } from "../api.js";
import {
  SOURCE_LABELS,
  STAGE_LABELS,
  TERMINAL_STAGES,
  stageColor,
} from "../constants.js";
import { daysSince, fmtDate, fmtPct } from "../format.js";
import Modal from "./Modal.jsx";
import AddApplicationForm from "./AddApplicationForm.jsx";
import LogEventForm from "./LogEventForm.jsx";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "offers", label: "Offers" },
  { id: "closed", label: "Closed" },
];

function matchesFilter(app, filter) {
  const stage = app.current_stage;
  if (filter === "active") return !TERMINAL_STAGES.has(stage);
  if (filter === "offers") return stage === "offer";
  if (filter === "closed") return stage === "rejected" || stage === "withdrawn";
  return true;
}

function StageBadge({ stage }) {
  if (!stage) return <span className="cell-muted">—</span>;
  return (
    <span className="stage">
      <span className="stage-dot" style={{ background: stageColor(stage) }} aria-hidden />
      {STAGE_LABELS[stage]}
    </span>
  );
}

export default function ApplicationsView({ apps, loadError, reload, notify }) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [eventFor, setEventFor] = useState(null);
  const [deleteFor, setDeleteFor] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const filtered = useMemo(() => {
    if (!apps) return [];
    const q = query.trim().toLowerCase();
    return apps.filter(
      (a) =>
        matchesFilter(a, filter) &&
        (!q ||
          a.company_name.toLowerCase().includes(q) ||
          a.role_title.toLowerCase().includes(q))
    );
  }, [apps, filter, query]);

  const counts = useMemo(() => {
    const c = { all: 0, active: 0, offers: 0, closed: 0 };
    for (const a of apps ?? []) {
      for (const f of FILTERS) if (matchesFilter(a, f.id)) c[f.id] += 1;
    }
    return c;
  }, [apps]);

  const responseRate = useMemo(() => {
    if (!apps?.length) return null;
    const responded = apps.filter((a) => a.current_stage !== "applied").length;
    return responded / apps.length;
  }, [apps]);

  async function confirmDelete() {
    setDeleting(true);
    try {
      await api.deleteApplication(deleteFor.id);
      notify(`Deleted ${deleteFor.company_name} — ${deleteFor.role_title}`);
      setDeleteFor(null);
      reload();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Applications</h1>
          <p className="page-sub">Every application, with its current stage derived from the event log.</p>
        </div>
        <button className="btn btn-accent" onClick={() => setAddOpen(true)}>
          <Plus size={16} weight="bold" aria-hidden /> Add application
        </button>
      </div>

      {loadError && (
        <div className="error-banner" role="alert">
          <WarningCircle size={18} aria-hidden />
          Couldn’t reach the API: {loadError}
          <button className="btn btn-ghost" onClick={reload}>
            <ArrowClockwise size={15} aria-hidden /> Retry
          </button>
        </div>
      )}

      <div className="tiles">
        <div className="tile">
          <div className="tile-label">Total</div>
          <div className="tile-value num">{apps ? apps.length : "–"}</div>
          <div className="tile-hint">applications tracked</div>
        </div>
        <div className="tile">
          <div className="tile-label">Active</div>
          <div className="tile-value num">{apps ? counts.active : "–"}</div>
          <div className="tile-hint">still in the pipeline</div>
        </div>
        <div className="tile">
          <div className="tile-label">Offers</div>
          <div className="tile-value num">{apps ? counts.offers : "–"}</div>
          <div className="tile-hint">reached offer stage</div>
        </div>
        <div className="tile">
          <div className="tile-label">Response rate</div>
          <div className="tile-value num">{responseRate == null ? "–" : fmtPct(responseRate)}</div>
          <div className="tile-hint">heard back beyond “applied”</div>
        </div>
      </div>

      <div className="filters">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            className={`chip ${filter === f.id ? "active" : ""}`}
            onClick={() => setFilter(f.id)}
            aria-pressed={filter === f.id}
          >
            {f.label}
            {apps && <span className="num">{counts[f.id]}</span>}
          </button>
        ))}
        <label className="search">
          <MagnifyingGlass size={15} aria-hidden />
          <input
            type="search"
            placeholder="Search company or role"
            aria-label="Search company or role"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>

      <div className="card">
        {!apps && !loadError ? (
          <div style={{ padding: 16, display: "grid", gap: 10 }}>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="skeleton" style={{ height: 44 }} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty">
            <div className="empty-icon">
              <Briefcase size={36} aria-hidden />
            </div>
            {apps?.length ? (
              <>
                <h3>Nothing matches</h3>
                <p>No applications match this filter or search.</p>
              </>
            ) : (
              <>
                <h3>No applications yet</h3>
                <p>Log your first application and every stage change from here on — the analytics build themselves.</p>
                <button className="btn btn-accent" onClick={() => setAddOpen(true)}>
                  <Plus size={16} weight="bold" aria-hidden /> Add your first application
                </button>
              </>
            )}
          </div>
        ) : (
          <div className="table-wrap">
            <table className="apps">
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Role</th>
                  <th>Source</th>
                  <th>Added</th>
                  <th>Stage</th>
                  <th>In stage</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((app) => {
                  const inStage = daysSince(app.current_stage_at);
                  return (
                    <tr key={app.id}>
                      <td>
                        <div className="co">
                          <div className="co-avatar" aria-hidden>
                            {app.company_name.slice(0, 1).toUpperCase()}
                          </div>
                          <span className="co-name">{app.company_name}</span>
                        </div>
                      </td>
                      <td className="co-role">{app.role_title}</td>
                      <td className="cell-muted">{SOURCE_LABELS[app.source]}</td>
                      <td className="cell-muted num">{fmtDate(app.created_at)}</td>
                      <td><StageBadge stage={app.current_stage} /></td>
                      <td className="cell-muted num">
                        {inStage == null ? "—" : `${inStage}d`}
                      </td>
                      <td>
                        <div className="row-actions">
                          <button
                            className="icon-btn"
                            onClick={() => setEventFor(app)}
                            aria-label={`Log stage event for ${app.company_name} ${app.role_title}`}
                            title="Log stage event"
                          >
                            <TrendUp size={17} />
                          </button>
                          <button
                            className="icon-btn danger"
                            onClick={() => setDeleteFor(app)}
                            aria-label={`Delete ${app.company_name} ${app.role_title}`}
                            title="Delete application"
                          >
                            <Trash size={17} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {addOpen && (
        <AddApplicationForm
          onClose={() => setAddOpen(false)}
          onSaved={(app) => {
            setAddOpen(false);
            notify(`Added ${app.company_name} — ${app.role_title}`);
            reload();
          }}
        />
      )}

      {eventFor && (
        <LogEventForm
          app={eventFor}
          onClose={() => setEventFor(null)}
          onSaved={(stage) => {
            setEventFor(null);
            notify(`${eventFor.company_name} moved to ${STAGE_LABELS[stage]}`);
            reload();
          }}
        />
      )}

      {deleteFor && (
        <Modal
          title="Delete application?"
          onClose={() => setDeleteFor(null)}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setDeleteFor(null)}>
                Cancel
              </button>
              <button className="btn btn-danger" onClick={confirmDelete} disabled={deleting}>
                {deleting ? "Deleting…" : "Delete permanently"}
              </button>
            </>
          }
        >
          <p style={{ margin: 0 }}>
            <strong>{deleteFor.company_name} — {deleteFor.role_title}</strong> and its
            entire stage history will be permanently removed. This can’t be undone.
          </p>
        </Modal>
      )}
    </main>
  );
}
