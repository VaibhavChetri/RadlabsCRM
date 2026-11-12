// AddLeadForm.jsx
// ---------------
// Add one lead by hand (POST /leads). Needs a name and at least one of
// email / phone. The new lead starts as "New" and is owned by you.

import { useState } from 'react';
import api from '../api';

const EMPTY = { first_name: '', last_name: '', company: '', email: '', phone: '' };

function errorMessage(err) {
  const detail = err.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg.replace(/^Value error, /, '')).join('. ');
  }
  if (typeof detail === 'string') return detail;
  return 'Could not add the lead. Please try again.';
}

export default function AddLeadForm({ onAdded }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
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
      setError(errorMessage(err));
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
      <button type="submit" className="inline" disabled={saving}>
        {saving ? 'Adding…' : 'Add lead'}
      </button>
    </form>
  );
}
