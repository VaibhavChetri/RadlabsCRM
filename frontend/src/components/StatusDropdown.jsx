// StatusDropdown.jsx
// ------------------
// A little dropdown on each lead row. Changing it calls
// PATCH /leads/{id}/status and tells the parent to update the screen.

import { useState } from 'react';
import api from '../api';

export default function StatusDropdown({ lead, onChanged }) {
  const [saving, setSaving] = useState(false);

  const handleChange = async (e) => {
    const newStatus = e.target.value;
    setSaving(true);
    try {
      await api.patch(`/leads/${lead.id}/status`, { status: newStatus });
      onChanged(lead.id, newStatus);   // update the table in place
    } catch {
      alert('Could not update status. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <select value={lead.status} onChange={handleChange} disabled={saving}>
      <option value="new">New</option>
      <option value="contacted">Contacted</option>
      <option value="closed">Closed</option>
    </select>
  );
}
