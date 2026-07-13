import { useState } from "react";
import { api } from "../api.js";
import { STAGES } from "../constants.js";
import Modal from "./Modal.jsx";

const PIPELINE = ["applied", "oa", "phone_screen", "interview", "final_round", "offer"];

function nextStage(current) {
  const i = PIPELINE.indexOf(current);
  return i >= 0 && i < PIPELINE.length - 1 ? PIPELINE[i + 1] : "interview";
}

export default function LogEventForm({ app, onClose, onSaved }) {
  const today = new Date().toISOString().slice(0, 10);
  const [stage, setStage] = useState(nextStage(app.current_stage));
  const [occurredOn, setOccurredOn] = useState(today);
  const [notes, setNotes] = useState("");
  const [backfill, setBackfill] = useState(false);
  const [needsBackfill, setNeedsBackfill] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [saving, setSaving] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setSaving(true);
    setSubmitError(null);
    try {
      await api.addEvent(
        app.id,
        {
          stage,
          // End-of-day local so an event dated today sorts after this morning's events.
          occurred_at: new Date(`${occurredOn}T23:59:00`).toISOString(),
          notes: notes.trim() || null,
        },
        backfill
      );
      onSaved(stage);
    } catch (err) {
      if (err.status === 409) {
        setNeedsBackfill(true);
        setSubmitError(
          "This date is earlier than the latest logged event. Tick “log as backfill” to record it anyway."
        );
      } else {
        setSubmitError(err.message);
      }
      setSaving(false);
    }
  }

  return (
    <Modal
      title={`Log stage — ${app.company_name}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} type="button">
            Cancel
          </button>
          <button className="btn btn-accent" type="submit" form="log-event-form" disabled={saving}>
            {saving ? "Logging…" : "Log event"}
          </button>
        </>
      }
    >
      <form id="log-event-form" onSubmit={submit} noValidate>
        {submitError && (
          <div className="form-alert" role="alert">{submitError}</div>
        )}
        <div className="field">
          <label htmlFor="e-stage">Stage</label>
          <select id="e-stage" value={stage} onChange={(e) => setStage(e.target.value)}>
            {STAGES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <div className="hint">
            Events are append-only — the latest one becomes the current stage.
          </div>
        </div>
        <div className="field">
          <label htmlFor="e-date">Happened on</label>
          <input
            id="e-date"
            type="date"
            max={today}
            value={occurredOn}
            onChange={(e) => setOccurredOn(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="e-notes">Notes</label>
          <textarea
            id="e-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Interviewer names, format, how it went"
          />
        </div>
        {needsBackfill && (
          <label className="checkbox">
            <input
              type="checkbox"
              checked={backfill}
              onChange={(e) => setBackfill(e.target.checked)}
            />
            <span>
              Log as backfill — records this event in the past without becoming the
              current stage if newer events exist.
            </span>
          </label>
        )}
      </form>
    </Modal>
  );
}
