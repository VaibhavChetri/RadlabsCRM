// Dashboard.jsx
// -------------
// The real dashboard. On load it fetches the logged-in client's leads
// (GET /leads/), shows them in a table, lets you change each lead's status,
// and download everything as Excel (GET /leads/export).

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import LeadsTable from '../components/LeadsTable';
import StatsOverview from '../components/StatsOverview';

export default function Dashboard() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);
  const navigate = useNavigate();

  // Fetch the leads once, when the page first loads.
  useEffect(() => {
    const loadLeads = async () => {
      try {
        const res = await api.get('/leads/');
        setLeads(res.data);
      } catch (err) {
        // If the token is missing/expired the server says 401 -> log out.
        if (err.response && err.response.status === 401) {
          localStorage.removeItem('token');
          navigate('/login');
          return;
        }
        setError('Could not load leads. Is the backend running?');
      } finally {
        setLoading(false);
      }
    };
    loadLeads();
  }, [navigate]);

  // When a row's status changes, update it in our local list so the screen
  // reflects it immediately (no full reload needed).
  const handleStatusChange = (leadId, newStatus) => {
    setLeads((prev) =>
      prev.map((l) => (l.id === leadId ? { ...l, status: newStatus } : l))
    );
  };

  // Download the Excel file. We must fetch it as a "blob" (raw file bytes)
  // and then trick the browser into downloading it.
  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await api.get('/leads/export', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'leads.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Could not export leads.');
    } finally {
      setExporting(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/login');
  };

  return (
    <div className="page">
      <header className="topbar">
        <h1>My Leads</h1>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            className="secondary"
            onClick={handleExport}
            disabled={exporting || leads.length === 0}
          >
            {exporting ? 'Exporting…' : 'Export to Excel'}
          </button>
          <button className="secondary" onClick={handleLogout}>Log out</button>
        </div>
      </header>

      <StatsOverview />

      <div className="card">
        {loading && <p className="hint">Loading your leads…</p>}

        {!loading && error && <div className="error">{error}</div>}

        {!loading && !error && leads.length === 0 && (
          <p className="hint">
            No leads yet. When your website contact form is submitted, leads
            will show up here. 📭
          </p>
        )}

        {!loading && !error && leads.length > 0 && (
          <LeadsTable leads={leads} onStatusChange={handleStatusChange} />
        )}
      </div>
    </div>
  );
}
