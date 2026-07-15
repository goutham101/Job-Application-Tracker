import { useCallback, useEffect, useState } from "react";
import {
  ArrowClockwise,
  Check,
  EnvelopeSimple,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import { api } from "../api.js";
import { STAGE_LABELS, stageColor } from "../constants.js";
import { fmtDate } from "../format.js";

function MatchRow({ match, applications, onResolved, notify }) {
  const [selectedAppId, setSelectedAppId] = useState("");
  const [busy, setBusy] = useState(false);

  const matchedApp = applications?.find((a) => a.id === match.application_id);

  async function confirm() {
    const appId = match.application_id ?? (selectedAppId ? Number(selectedAppId) : null);
    if (!appId) {
      notify("Pick an application to link this email to first", "error");
      return;
    }
    setBusy(true);
    try {
      await api.confirmMatch(match.id, appId);
      notify(`Logged ${STAGE_LABELS[match.suggested_stage]} from email`);
      onResolved(match.id);
    } catch (err) {
      notify(err.message, "error");
      setBusy(false);
    }
  }

  async function dismiss() {
    setBusy(true);
    try {
      await api.dismissMatch(match.id);
      notify("Dismissed");
      onResolved(match.id);
    } catch (err) {
      notify(err.message, "error");
      setBusy(false);
    }
  }

  return (
    <div className="match-row">
      <div className="match-main">
        <div className="match-top">
          <span className="stage">
            <span
              className="stage-dot"
              style={{ background: stageColor(match.suggested_stage) }}
              aria-hidden
            />
            Suggests: {STAGE_LABELS[match.suggested_stage]}
          </span>
          <span className="cell-muted num">{fmtDate(match.received_at)}</span>
        </div>
        <div className="match-subject">{match.subject}</div>
        <div className="cell-muted">{match.sender}</div>
      </div>
      <div className="match-actions">
        {matchedApp ? (
          <div className="match-linked">
            Linked to <strong>{matchedApp.company_name}</strong> — {matchedApp.role_title}
          </div>
        ) : (
          <select
            value={selectedAppId}
            onChange={(e) => setSelectedAppId(e.target.value)}
            aria-label={`Link "${match.subject}" to an application`}
          >
            <option value="">Link to application…</option>
            {applications?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.company_name} — {a.role_title}
              </option>
            ))}
          </select>
        )}
        <div className="match-buttons">
          <button className="btn btn-accent" onClick={confirm} disabled={busy}>
            <Check size={15} weight="bold" aria-hidden /> Confirm
          </button>
          <button className="btn btn-ghost" onClick={dismiss} disabled={busy}>
            <X size={15} aria-hidden /> Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}

export default function MatchesView({ notify }) {
  const [matches, setMatches] = useState(null);
  const [applications, setApplications] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [m, a] = await Promise.all([api.listMatches(), api.listApplications()]);
      setMatches(m);
      setApplications(a);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleResolved = (id) => {
    setMatches((prev) => prev?.filter((m) => m.id !== id) ?? null);
  };

  if (error) {
    return (
      <main className="page">
        <div className="error-banner" role="alert">
          <WarningCircle size={18} aria-hidden />
          Couldn’t load the review queue: {error}
          <button className="btn btn-ghost" onClick={load}>
            <ArrowClockwise size={15} aria-hidden /> Retry
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Review Queue</h1>
          <p className="page-sub">
            Emails matched from Gmail, waiting for your confirmation before anything is logged.
          </p>
        </div>
      </div>

      {!matches ? (
        <div style={{ display: "grid", gap: 10 }}>
          {[0, 1].map((i) => (
            <div key={i} className="skeleton" style={{ height: 90 }} />
          ))}
        </div>
      ) : matches.length === 0 ? (
        <div className="card">
          <div className="empty">
            <div className="empty-icon">
              <EnvelopeSimple size={36} aria-hidden />
            </div>
            <h3>Nothing to review</h3>
            <p>
              Once the Gmail poller finds a rejection or interview email, it’ll show up here for
              you to confirm before it touches your applications.
            </p>
          </div>
        </div>
      ) : (
        <div className="matches-list">
          {matches.map((m) => (
            <MatchRow
              key={m.id}
              match={m}
              applications={applications}
              onResolved={handleResolved}
              notify={notify}
            />
          ))}
        </div>
      )}
    </main>
  );
}
