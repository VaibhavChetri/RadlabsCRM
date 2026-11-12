// AddLeadForm.jsx
// ---------------
// Add one lead by hand (POST /leads). Needs a name and at least one of
// email / phone. The new lead starts as "New" and is owned by you.
// If the person is already in the CRM (same email, phone or LinkedIn), the
// API answers 409 and the form offers to open the existing lead instead.

import { useState } from 'react';
import api from '../api';
import { errorMessage } from '../format';

const EMPTY = { first_name: '', last_name: '', company: '', email: '', phone: '' };

export default function AddLeadForm({ onAdded, onOpenExisting }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [existing, setExisting] = useState(null); // { lead_uuid, name } on a 409

  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setExisting(null);
    if (!form.email.trim() && !form.phone.trim()) {
      setError('Enter an email or a phone number.');
      return;
    }
    setSaving(true);
    try {
      await api.post('/leads', form);
      setForm(EMPTY);
      onAdded();
    } catch (err) {
      if (err.response?.status === 409) setExisting(err.response.data.detail);
      else setError(errorMessage(err, 'Could not add the lead. Please try again.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="card add-lead" onSubmit={handleSubmit}>
      <h2>Add lead</h2>
      <div className="form-grid">
        <label>
          First name
          <input value={form.first_name} onChange={update('first_name')} required />
        </label>
        <label>
          Last name
          <input value={form.last_name} onChange={update('last_name')} />
        </label>
        <label>
          Company
          <input value={form.company} onChange={update('company')} />
        </label>
        <label>
          Email
          <input type="email" value={form.email} onChange={update('email')} />
        </label>
        <label>
          Phone
          <input type="tel" value={form.phone} onChange={update('phone')} />
        </label>
      </div>
      {error && <div className="error">{error}</div>}
      {existing && (
        <div className="error">
          {existing.name || 'This person'} is already in the CRM.{' '}
          <button type="button" className="link-btn" onClick={() => onOpenExisting(existing.lead_uuid)}>
            Open the existing lead
          </button>
        </div>
      )}
      <button type="submit" className="inline" disabled={saving}>
        {saving ? 'Adding…' : 'Add lead'}
      </button>
    </form>
  );
}
