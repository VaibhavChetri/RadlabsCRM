// Home.jsx
// --------
// "My call list today" (route /). Only the leads I own, in the order I work them:
//   Overdue    follow-up date already passed (red), oldest first
//   Due today  follow-up date is today, Hot first
//   New        my New leads with no follow-up due yet, Hot first
// Won / Lost / Not interested / Do not call never show here.
// Each row has +1 Call and a status dropdown; after either, the list reloads
// (a lead may move to another section or leave the list).
// The analytics strip (Me / Team, This week / This month / Custom) sits above the list.
// Below the call list, "My leads": every lead I own, any status, newest first
// (first MY_LEADS_SHOWN; the link opens the full list in All leads).

import { useCallback, useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import api from '../api';
import AnalyticsStrip from '../components/AnalyticsStrip';
import Button from '../components/Button';
import {
  PRIORITY_LABELS, errorMessage, formatDate, formatShortDateTime, fullName, localDateISO,
} from '../format';

const SECTIONS = [
  ['overdue', 'Overdue follow-ups', 'Nothing overdue. Good work.'],
  ['due_today', 'Follow-ups due today', 'No follow-ups due today.'],
  ['new', 'New leads', 'No new leads assigned to you.'],
];

const MY_LEADS_SHOWN = 50;

const TABLE_HEAD = (
  <thead>
    <tr>
      <th>Name</th>
      <th>Company</th>
      <th>Phone</th>
      <th>Priority</th>
      <th>Status</th>
      <th>Calls</th>
      <th>Last called</th>
      <th>Follow-up</th>
    </tr>
  </thead>
);

function CallRow({ lead, statuses, overdue, busy, onCall, onStatus }) {
  return (
    <tr className={overdue ? 'row-overdue' : undefined}>
      <td className="cell-title">
        <Link to={`/leads/${lead.uuid}`}>{fullName(lead) || 'Unnamed lead'}</Link>
        {lead.job_title && <div className="muted small">{lead.job_title}</div>}
      </td>
      <td data-label="Company">{lead.company || <span className="muted">—</span>}</td>
      <td data-label="Phone">
        {lead.phone
          ? <a href={`tel:${lead.phone.replace(/[^\d+]/g, '')}`}>{lead.phone}</a>
          : <span className="muted">No phone</span>}
      </td>
      <td data-label="Priority"><span className={`badge priority-${lead.priority}`}>{PRIORITY_LABELS[lead.priority]}</span></td>
      <td data-label="Status">
        <select className="compact" value={lead.status} disabled={busy}
          onChange={(e) => onStatus(lead, e.target.value)}>
          {statuses.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
        </select>
      </td>
      <td data-label="Calls">
        <span className="input-row">
          <Button variant="call" size="sm" icon="phone" loading={busy} onClick={() => onCall(lead)}>
            +1 Call
          </Button>
          <span className="muted">{lead.call_attempts}</span>
        </span>
      </td>
      <td data-label="Last called" className="muted">
        {lead.last_called_at ? formatShortDateTime(lead.last_called_at) : 'Never'}
      </td>
      <td data-label="Follow-up" className={overdue ? 'overdue-date' : undefined}>
        {lead.next_follow_up ? formatDate(lead.next_follow_up) : <span className="muted">None</span>}
      </td>
    </tr>
  );
}

export default function Home() {
  const { me } = useOutletContext();
  const [sections, setSections] = useState(null);
  const [myLeads, setMyLeads] = useState(null); // { items, total }
  const [statuses, setStatuses] = useState([]);
  const [loadError, setLoadError] = useState('');
  const [error, setError] = useState('');
  const [busyUuid, setBusyUuid] = useState(null);
  const [statsKey, setStatsKey] = useState(0); // bump to reload the analytics strip

  // "Today" is the caller's local date, not the server's.
  const loadList = useCallback(
    () => api.get('/leads/today', { params: { today: localDateISO() } })
      .then((res) => { setSections(res.data); setLoadError(''); }),
    [],
  );

  const myUuid = me?.uuid;
  const loadMine = useCallback(() => {
    if (!myUuid) return Promise.resolve();
    return api.get('/leads', {
      params: { owner: myUuid, sort: 'added', order: 'desc', page_size: MY_LEADS_SHOWN },
    }).then((res) => setMyLeads(res.data));
  }, [myUuid]);

  useEffect(() => {
    loadMine().catch(() => setLoadError('Could not load your leads. Is the backend running?'));
  }, [loadMine]);

  useEffect(() => {
    Promise.all([loadList(), api.get('/statuses').then((res) => setStatuses(res.data))])
      .catch(() => setLoadError('Could not load your call list. Is the backend running?'));
  }, [loadList]);

  // Run one change on a row, then reload the whole list.
  const act = async (lead, request) => {
    setError('');
    setBusyUuid(lead.uuid);
    try {
      await request();
      await Promise.all([loadList(), loadMine()]);
      setStatsKey((k) => k + 1);
    } catch (err) {
      setError(errorMessage(err, 'Could not save. Please try again.'));
    } finally {
      setBusyUuid(null);
    }
  };

  const handleCall = (lead) => act(lead, () => api.post(`/leads/${lead.uuid}/call`));
  const handleStatus = (lead, status) => act(lead, () => api.patch(`/leads/${lead.uuid}`, { status }));

  if (loadError) return <div className="card"><div className="error">{loadError}</div></div>;
  if (!sections) return <p className="hint">Loading your call list…</p>;

  const total = SECTIONS.reduce((n, [key]) => n + sections[key].length, 0);

  return (
    <>
      <AnalyticsStrip refreshKey={statsKey} />

      <div className="lead-head">
        <div>
          <h1>My call list today</h1>
          <p className="subtitle">
            {total === 0 ? 'Nothing to call right now.' : `${total} ${total === 1 ? 'lead' : 'leads'} to work`}
          </p>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      {SECTIONS.map(([key, title, emptyText]) => (
        <div className="card" key={key}>
          <div className="card-head">
            <h2 className={key === 'overdue' && sections.overdue.length ? 'overdue-title' : undefined}>
              {title}
            </h2>
            <span className="muted">{sections[key].length}</span>
          </div>
          {sections[key].length === 0 ? (
            <p className="muted">{emptyText}</p>
          ) : (
            <div className="table-wrap">
              <table className="stack-table">
                {TABLE_HEAD}
                <tbody>
                  {sections[key].map((lead) => (
                    <CallRow key={lead.uuid} lead={lead} statuses={statuses}
                      overdue={key === 'overdue'} busy={busyUuid === lead.uuid}
                      onCall={handleCall} onStatus={handleStatus} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}

      <div className="card">
        <div className="card-head">
          <h2>My leads</h2>
          <span className="muted">{myLeads ? myLeads.total : ''}</span>
        </div>
        <p className="muted small">Every lead you own, any status, newest first.</p>
        {!myLeads ? (
          <p className="muted">Loading your leads…</p>
        ) : myLeads.total === 0 ? (
          <p className="muted">You do not own any leads yet.</p>
        ) : (
          <>
            <div className="table-wrap">
              <table className="stack-table">
                {TABLE_HEAD}
                <tbody>
                  {myLeads.items.map((lead) => (
                    <CallRow key={lead.uuid} lead={lead} statuses={statuses}
                      overdue={false} busy={busyUuid === lead.uuid}
                      onCall={handleCall} onStatus={handleStatus} />
                  ))}
                </tbody>
              </table>
            </div>
            {myLeads.total > myLeads.items.length && (
              <p className="muted small">
                Showing the newest {myLeads.items.length} of {myLeads.total}.{' '}
                <Link to={`/leads?owner=${myUuid}`}>See all my leads in All leads →</Link>
              </p>
            )}
          </>
        )}
      </div>
    </>
  );
}
