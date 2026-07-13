import { useState } from "react";
import { api } from "../api.js";
import { SOURCES } from "../constants.js";
import Modal from "./Modal.jsx";

function toIso(dateStr) {
  // Interpret the picked date as noon local time so timezones can't shift the day.
  return dateStr ? new Date(`${dateStr}T12:00:00`).toISOString() : undefined;
}

export default function AddApplicationForm({ onClose, onSaved }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    company_name: "",
    role_title: "",
    source: "cold_apply",
    applied_on: today,
    job_url: "",
    notes: "",
  });
  const [touched, setTouched] = useState({});
  const [submitError, setSubmitError] = useState(null);
  const [saving, setSaving] = useState(false);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const blur = (key) => () => setTouched({ ...touched, [key]: true });

  const errors = {
    company_name: form.company_name.trim() ? null : "Company is required",
    role_title: form.role_title.trim() ? null : "Role is required",
  };
  const invalid = Object.values(errors).some(Boolean);

  async function submit(e) {
    e.preventDefault();
    setTouched({ company_name: true, role_title: true });
    if (invalid) return;
    setSaving(true);
    setSubmitError(null);
    try {
      const app = await api.createApplication({
        company_name: form.company_name.trim(),
        role_title: form.role_title.trim(),
        source: form.source,
        applied_at: toIso(form.applied_on),
        job_url: form.job_url.trim() || null,
        notes: form.notes.trim() || null,
      });
      onSaved(app);
    } catch (err) {
      setSubmitError(err.message);
      setSaving(false);
    }
  }

  const fieldClass = (key) => `field ${touched[key] && errors[key] ? "invalid" : ""}`;

  return (
    <Modal
      title="Add application"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} type="button">
            Cancel
          </button>
          <button className="btn btn-accent" type="submit" form="add-app-form" disabled={saving}>
            {saving ? "Saving…" : "Add application"}
          </button>
        </>
      }
    >
      <form id="add-app-form" onSubmit={submit} noValidate>
        {submitError && (
          <div className="form-alert" role="alert">{submitError}</div>
        )}
        <div className={fieldClass("company_name")}>
          <label htmlFor="f-company">
            Company <span className="req" aria-hidden>*</span>
          </label>
          <input
            id="f-company"
            value={form.company_name}
            onChange={set("company_name")}
            onBlur={blur("company_name")}
            autoComplete="organization"
            required
          />
          {touched.company_name && errors.company_name && (
            <div className="field-error">{errors.company_name}</div>
          )}
        </div>
        <div className={fieldClass("role_title")}>
          <label htmlFor="f-role">
            Role <span className="req" aria-hidden>*</span>
          </label>
          <input
            id="f-role"
            value={form.role_title}
            onChange={set("role_title")}
            onBlur={blur("role_title")}
            placeholder="e.g. Software Engineer Intern"
            required
          />
          {touched.role_title && errors.role_title && (
            <div className="field-error">{errors.role_title}</div>
          )}
        </div>
        <div className="field-row">
          <div className="field">
            <label htmlFor="f-source">Source</label>
            <select id="f-source" value={form.source} onChange={set("source")}>
              {SOURCES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-applied">Applied on</label>
            <input
              id="f-applied"
              type="date"
              max={today}
              value={form.applied_on}
              onChange={set("applied_on")}
            />
          </div>
        </div>
        <div className="field">
          <label htmlFor="f-url">Job posting URL</label>
          <input
            id="f-url"
            type="url"
            inputMode="url"
            placeholder="https://…"
            value={form.job_url}
            onChange={set("job_url")}
          />
        </div>
        <div className="field">
          <label htmlFor="f-notes">Notes</label>
          <textarea
            id="f-notes"
            value={form.notes}
            onChange={set("notes")}
            placeholder="Referrer, salary range, anything worth remembering"
          />
        </div>
      </form>
    </Modal>
  );
}
