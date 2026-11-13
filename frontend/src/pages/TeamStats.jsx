// TeamStats.jsx
// -------------
// Team stats (route /stats): one row per person for the chosen period.
//   Calls, Meetings booked, Won   what that person did in the period
//   Leads + one column per stage  the leads they own now, by current status
// Deactivated people show (greyed) when they did something in the period,
// so past periods keep their history. Data: GET /stats/team.

import { useEffect, useState } from 'react';
import api from '../api';
import PeriodPicker from '../components/PeriodPicker';
import { errorMessage, initialPeriod, tzOffsetMinutes } from '../format';

export default function TeamStats() {
  const [period, setPeriod] = useState(() => initialPeriod('week'));
  const [table, setTable] = useState(null);
  const [error, setError] = useState('');
  const requestKey = `${period.from}|${period.to}`;
  const [loadedKey, setLoadedKey] = useState(null);
  const loading = loadedKey !== requestKey;

  useEffect(() => {
    let current = true; // ignore an answer for a period no longer picked
    api.get('/stats/team', {
      params: { from: period.from, to: period.to, tz_offset: tzOffsetMinutes() },
    })
      .then((res) => { if (current) { setTable(res.data); setError(''); } })
      .catch((err) => { if (current) setError(errorMessage(err, 'Could not load team stats.')); })
      .finally(() => { if (current) setLoadedKey(requestKey); });
    return () => { current = false; };
  }, [period.from, period.to, requestKey]);

  const totals = table && {
    calls: table.rows.reduce((n, r) => n + r.calls, 0),
    meetings_booked: table.rows.reduce((n, r) => n + r.meetings_booked, 0),
    won: table.rows.reduce((n, r) => n + r.won, 0),
  };

  return (
    <>
      <div className="lead-head">
        <div>
          <h1>Team stats</h1>
          <p className="subtitle">Who is calling, and what it turns into.</p>
        </div>
      </div>

      <div className="stats-toolbar">
        <PeriodPicker value={period} onChange={setPeriod} />
      </div>

      {error && <div className="error">{error}</div>}
      {!table && !error && <p className="hint">Loading team stats…</p>}

      {table && (
        <div className="card">
          <div className={`table-wrap${loading ? ' is-loading' : ''}`}>
            <table className="team-table">
              <thead>
                <tr>
                  <th>Person</th>
                  <th className="num">Calls</th>
                  <th className="num">Meetings booked</th>
                  <th className="num">Won</th>
                  <th className="num col-split">Leads owned</th>
                  {table.statuses.map((s) => <th key={s} className="num">{s}</th>)}
                </tr>
                <tr className="table-group-row">
                  <th colSpan={4} className="muted small">In this period</th>
                  <th colSpan={table.statuses.length + 1} className="muted small col-split">
                    Now, by current status
                  </th>
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row) => (
                  <tr key={row.uuid} className={row.is_active ? undefined : 'row-inactive'}>
                    <td>
                      {row.name}
                      {!row.is_active && <span className="badge small-badge">Deactivated</span>}
                    </td>
                    <td className="num strong">{row.calls}</td>
                    <td className="num strong">{row.meetings_booked}</td>
                    <td className="num strong">{row.won}</td>
                    <td className="num col-split">{row.leads}</td>
                    {table.statuses.map((s) => (
                      <td key={s} className={`num${row.by_status[s] ? '' : ' muted'}`}>
                        {row.by_status[s]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td>Team</td>
                  <td className="num">{totals.calls}</td>
                  <td className="num">{totals.meetings_booked}</td>
                  <td className="num">{totals.won}</td>
                  <td colSpan={table.statuses.length + 1} className="col-split" />
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
