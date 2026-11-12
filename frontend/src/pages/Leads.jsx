// Leads.jsx
// ---------
// Phase 1 "All leads": a simple Add-lead form and the list of every lead
// with its "Added to CRM" date and who added it. A name opens the lead.
// Search, filters, paging and bulk actions arrive in Phase 4.

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';
import AddLeadForm from '../components/AddLeadForm';
import { DO_NOT_CALL, formatDateTime, fullName } from '../format';

export default function Leads() {
  const [leads, setLeads] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    api
      .get('/leads')
      .then((res) => {
        setLeads(res.data.items);
        setTotal(res.data.total);
        setError('');
      })
      .catch(() => setError('Could not load leads. Is the backend running?'))
      .finally(() => setLoading(false));
  }, [reloadKey]);

  return (
    <>
      <AddLeadForm onAdded={() => setReloadKey((k) => k + 1)} />

      <div className="card">
        <div className="card-head">
          <h2>All leads</h2>
          <span className="muted">{total} total</span>
        </div>

        {loading && <p className="hint">Loading leads…</p>}
        {!loading && error && <div className="error">{error}</div>}
        {!loading && !error && leads.length === 0 && (
          <p className="hint">No leads yet. Add your first lead above.</p>
        )}

        {!loading && !error && leads.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Company</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>Status</th>
                  <th>Owner</th>
                  <th>Added to CRM</th>
                  <th>Added by</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.uuid}>
                    <td><Link to={`/leads/${lead.uuid}`}>{fullName(lead)}</Link></td>
                    <td>{lead.company}</td>
                    <td>{lead.email}</td>
                    <td>{lead.phone}</td>
                    <td>
                      <span className={lead.status === DO_NOT_CALL ? 'badge danger' : 'badge'}>
                        {lead.status}
                      </span>
                    </td>
                    <td>{lead.owner || <span className="muted">Unassigned</span>}</td>
                    <td>{formatDateTime(lead.created_at)}</td>
                    <td>{lead.created_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
