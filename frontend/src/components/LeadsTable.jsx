// LeadsTable.jsx
// --------------
// Renders the list of leads in a table. Each row has a StatusDropdown so the
// client can move a lead through new -> contacted -> closed.

import StatusDropdown from './StatusDropdown';

// Turn the backend timestamp into something human-friendly.
function formatDate(value) {
  if (!value) return '';
  const d = new Date(value);
  if (isNaN(d)) return value;
  return d.toLocaleString();
}

export default function LeadsTable({ leads, onStatusChange }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Email</th>
          <th>Phone</th>
          <th>Message</th>
          <th>Status</th>
          <th>Submitted</th>
        </tr>
      </thead>
      <tbody>
        {leads.map((lead) => (
          <tr key={lead.id}>
            <td>{lead.name}</td>
            <td>{lead.email}</td>
            <td>{lead.phone}</td>
            <td>{lead.message}</td>
            <td>
              <StatusDropdown lead={lead} onChanged={onStatusChange} />
            </td>
            <td>{formatDate(lead.submitted_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
