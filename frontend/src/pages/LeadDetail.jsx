// LeadDetail.jsx
// --------------
// One lead, everything about it (route /leads/:uuid).
//   Details   every person/company field, edited in a form, "Save changes".
//   Pipeline  Status, Priority, Owner: each saves as soon as it changes.
//   Calls     "+1 Call", attempts, Last called, Next follow-up date.
//   Notes     one box, "Stamp" adds "[DD Mon HH:MM · Name] " at the top.
//   Delete    asks first.
// Every save is a PATCH (or POST /call); the server writes the history.

import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import api from '../api';
import {
  DO_NOT_CALL, errorMessage, externalUrl, formatDateTime, fullName, whatsappUrl,
} from '../format';

const SOURCES = ['Apollo', 'LinkedIn', 'Referral', 'Event', 'Cold list', 'Other'];
const PRIORITIES = [['hot', 'Hot'], ['warm', 'Warm'], ['cold', 'Cold']];

// [field, label, input type] in the order they are shown.
const PERSON_FIELDS = [
  ['first_name', 'First name', 'text'],
  ['last_name', 'Last name', 'text'],
  ['job_title', 'Job title', 'text'],
  ['email', 'Email', 'email'],
  ['phone', 'Phone', 'tel'],
  ['phone_2', 'Second phone', 'tel'],
  ['linkedin_url', 'LinkedIn URL', 'url'],
];
const COMPANY_FIELDS = [
  ['company', 'Company', 'text'],
  ['website', 'Website', 'text'],
  ['industry', 'Industry', 'text'],
  ['company_size', 'Company size', 'text'],
  ['city', 'City', 'text'],
  ['country', 'Country', 'text'],
];
const FORM_FIELDS = [...PERSON_FIELDS, ...COMPANY_FIELDS].map(([f]) => f).concat('source');

function formFrom(lead) {
  return Object.fromEntries(FORM_FIELDS.map((f) => [f, lead[f] ?? '']));
}

// Tap-to-call + WhatsApp next to a phone number.
function PhoneLinks({ phone }) {
  if (!phone) return null;
  return (
    <span className="field-links">
      <a href={`tel:${phone.replace(/[^\d+]/g, '')}`}>Call</a>
      <a href={whatsappUrl(phone)} target="_blank" rel="noreferrer">WhatsApp</a>
    </span>
  );
}

function OpenLink({ url, label }) {
  if (!url) return null;
  return (
    <span className="field-links">
      <a href={externalUrl(url)} target="_blank" rel="noreferrer">{label}</a>
    </span>
  );
}

export default function LeadDetail() {
  const { uuid } = useParams();
  const navigate = useNavigate();
  const notesRef = useRef(null);

  const [lead, setLead] = useState(null);
  const [statuses, setStatuses] = useState([]);
  const [owners, setOwners] = useState([]);
  const [form, setForm] = useState(null);
  const [notes, setNotes] = useState('');
  const [loadError, setLoadError] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  // Show a fresh copy of the lead everywhere on the page.
  const showLead = (data) => {
    setLead(data);
    setForm(formFrom(data));
    setNotes(data.notes ?? '');
  };

  useEffect(() => {
    Promise.all([api.get(`/leads/${uuid}`), api.get('/statuses'), api.get('/owners')])
      .then(([leadRes, statusRes, ownerRes]) => {
        showLead(leadRes.data);
        setStatuses(statusRes.data);
        setOwners(ownerRes.data);
      })
      .catch((err) => setLoadError(
        err.response?.status === 404 ? 'This lead does not exist (it may have been deleted).'
          : 'Could not load the lead. Is the backend running?',
      ));
  }, [uuid]);

  // Run one save; show the server's answer or its error.
  const save = async (request) => {
    setError('');
    setBusy(true);
    try {
      const res = await request();
      showLead(res.data);
      return true;
    } catch (err) {
      setError(errorMessage(err, 'Could not save. Please try again.'));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const patch = (changes) => save(() => api.patch(`/leads/${uuid}`, changes));

  if (loadError) {
    return (
      <div className="card">
        <div className="error">{loadError}</div>
        <Link to="/leads">← Back to all leads</Link>
      </div>
    );
  }
  if (!lead || !form) return <p className="hint">Loading lead…</p>;

  const isDoNotCall = lead.status === DO_NOT_CALL;
  const formDirty = FORM_FIELDS.some((f) => form[f] !== (lead[f] ?? ''));
  const notesDirty = notes !== (lead.notes ?? '');
  // Keep a deactivated owner visible in the dropdown.
  const ownerOptions = lead.owner_uuid && !owners.some((o) => o.uuid === lead.owner_uuid)
    ? [...owners, { uuid: lead.owner_uuid, name: `${lead.owner} (inactive)` }]
    : owners;

  const updateField = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSaveDetails = (e) => {
    e.preventDefault();
    const changes = Object.fromEntries(
      FORM_FIELDS.filter((f) => form[f] !== (lead[f] ?? '')).map((f) => [f, form[f]]),
    );
    patch(changes);
  };

  const handleStamp = async () => {
    setError('');
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const res = await api.get('/leads/stamp', { params: { tz } });
      const stamp = res.data.text;
      setNotes((current) => (current ? `${stamp}\n${current}` : stamp));
      // Put the cursor right after the stamp, ready to type.
      requestAnimationFrame(() => {
        const box = notesRef.current;
        if (box) {
          box.focus();
          box.setSelectionRange(stamp.length, stamp.length);
        }
      });
    } catch (err) {
      setError(errorMessage(err, 'Could not add the stamp.'));
    }
  };

  const handleDelete = async () => {
    const name = fullName(lead) || 'this lead';
    if (!window.confirm(`Delete ${name}? Their calls and history are deleted too. This cannot be undone.`)) {
      return;
    }
    setBusy(true);
    try {
      await api.delete(`/leads/${uuid}`);
      navigate('/leads', { replace: true });
    } catch (err) {
      setError(errorMessage(err, 'Could not delete the lead.'));
      setBusy(false);
    }
  };

  const renderField = ([field, label, type]) => (
    <label key={field}>
      <span className="label-row">
        {label}
        {(field === 'phone' || field === 'phone_2') && <PhoneLinks phone={lead[field]} />}
        {field === 'linkedin_url' && <OpenLink url={lead.linkedin_url} label="Open profile" />}
        {field === 'website' && <OpenLink url={lead.website} label="Open site" />}
        {field === 'email' && lead.email && (
          <span className="field-links"><a href={`mailto:${lead.email}`}>Email</a></span>
        )}
      </span>
      <input type={type} value={form[field]} onChange={updateField(field)} />
    </label>
  );

  return (
    <>
      <Link to="/leads" className="back-link">← All leads</Link>

      <div className="lead-head">
        <div>
          <h1>{fullName(lead) || 'Unnamed lead'}</h1>
          <p className="subtitle">
            {[lead.job_title, lead.company].filter(Boolean).join(' · ') || 'No title or company yet'}
          </p>
        </div>
        <span className={isDoNotCall ? 'badge danger big' : 'badge big'}>{lead.status}</span>
      </div>

      {isDoNotCall && (
        <div className="dnc-banner">
          ⛔ Do not call. This lead asked not to be contacted. Do not call or message them.
        </div>
      )}
      {error && <div className="error">{error}</div>}

      <div className="detail-grid">
        <form className="card" onSubmit={handleSaveDetails}>
          <h2>Person</h2>
          <div className="form-grid">{PERSON_FIELDS.map(renderField)}</div>
          <h2>Company</h2>
          <div className="form-grid">
            {COMPANY_FIELDS.map(renderField)}
            <label>
              Source
              <select value={form.source} onChange={updateField('source')}>
                {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          </div>
          <div className="actions">
            <button type="submit" className="inline" disabled={busy || !formDirty}>
              Save changes
            </button>
            {formDirty && (
              <button type="button" className="secondary" onClick={() => setForm(formFrom(lead))}>
                Undo
              </button>
            )}
          </div>
        </form>

        <div>
          <div className="card">
            <h2>Pipeline</h2>
            <label>
              Status
              <select value={lead.status} disabled={busy}
                onChange={(e) => patch({ status: e.target.value })}>
                {statuses.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
              </select>
            </label>
            <label>
              Priority
              <select value={lead.priority} disabled={busy}
                onChange={(e) => patch({ priority: e.target.value })}>
                {PRIORITIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label>
              Owner
              <select value={lead.owner_uuid ?? ''} disabled={busy}
                onChange={(e) => patch({ owner_uuid: e.target.value || null })}>
                <option value="">Unassigned</option>
                {ownerOptions.map((o) => <option key={o.uuid} value={o.uuid}>{o.name}</option>)}
              </select>
            </label>
          </div>

          <div className="card">
            <h2>Calls</h2>
            <div className="call-row">
              <button type="button" className="inline" disabled={busy}
                onClick={() => save(() => api.post(`/leads/${uuid}/call`))}>
                +1 Call
              </button>
              <div>
                <div className="stat-value">{lead.call_attempts}</div>
                <div className="stat-label">{lead.call_attempts === 1 ? 'call' : 'calls'}</div>
              </div>
            </div>
            <p className="muted">
              Last called: {lead.last_called_at ? formatDateTime(lead.last_called_at) : 'never'}
            </p>
            <label>
              Next follow-up
              <span className="input-row">
                <input type="date" value={lead.next_follow_up ?? ''} disabled={busy}
                  onChange={(e) => patch({ next_follow_up: e.target.value || null })} />
                {lead.next_follow_up && (
                  <button type="button" className="secondary" disabled={busy}
                    onClick={() => patch({ next_follow_up: null })}>
                    Clear
                  </button>
                )}
              </span>
            </label>
          </div>

          <div className="card">
            <div className="card-head">
              <h2>Notes</h2>
              <button type="button" className="secondary" onClick={handleStamp}>Stamp</button>
            </div>
            <textarea ref={notesRef} rows={8} value={notes}
              placeholder="What did you learn on the call?"
              onChange={(e) => setNotes(e.target.value)} />
            <div className="actions">
              <button type="button" className="inline" disabled={busy || !notesDirty}
                onClick={() => patch({ notes })}>
                Save notes
              </button>
              {notesDirty && <span className="muted">Unsaved changes</span>}
            </div>
            <p className="muted">
              {lead.notes_updated_by
                ? `Last edited by ${lead.notes_updated_by} at ${formatDateTime(lead.notes_updated_at)}`
                : 'No notes yet'}
            </p>
          </div>

          <div className="card">
            <h2>Record</h2>
            <p className="muted">
              Added to CRM {formatDateTime(lead.created_at)}
              {lead.created_by && ` by ${lead.created_by}`}
            </p>
            <p className="muted">Last updated {formatDateTime(lead.updated_at)}</p>
            <button type="button" className="danger inline" disabled={busy} onClick={handleDelete}>
              Delete lead
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
