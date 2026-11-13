// AnalyticsStrip.jsx
// ------------------
// The numbers block on top of Home. Two toggles drive every card and chart:
//   Me / Team                         (Me = my calls, my leads, my stage moves)
//   This week / This month / Custom   (local dates, both ends included)
// Data: GET /stats/summary. Charts are plain CSS bars (no chart library).
//   Pipeline funnel   current status of every lead, all 10 stages
//   Calls per day     one bar per day of the period, empty days = 0
//   Leads added/day   same
//   Leads by source   leads added in the period

import { useEffect, useState } from 'react';
import api from '../api';
import {
  errorMessage, formatDate, formatDayShort, initialPeriod, tzOffsetMinutes,
} from '../format';
import PeriodPicker from './PeriodPicker';

const SCOPES = [['me', 'Me'], ['team', 'Team']];

// Open stages in blues, then the exits: Won green, the rest muted/red.
const STAGE_COLORS = {
  New: '#93c5fd',
  Attempted: '#60a5fa',
  Connected: '#3b82f6',
  Interested: '#2563eb',
  'Meeting booked': '#1d4ed8',
  'Proposal sent': '#1e40af',
  Won: '#16a34a',
  Lost: '#9ca3af',
  'Not interested': '#cbd5e1',
  'Do not call': '#dc2626',
};

function HBars({ rows, colorFor }) {
  const max = Math.max(...rows.map((r) => r.count), 1);
  return rows.map((r) => (
    <div className="funnel-row" key={r.label}>
      <span className="funnel-label">{r.label}</span>
      <div className="funnel-track">
        <div className="funnel-bar"
          style={{ width: `${(r.count / max) * 100}%`, background: colorFor(r) }} />
      </div>
      <span className="funnel-count">{r.count}</span>
    </div>
  ));
}

function DayBars({ days, unit }) {
  const max = Math.max(...days.map((d) => d.count), 0);
  const scale = Math.max(max, 1); // all-zero period: flat bars, no divide by 0
  const total = days.reduce((n, d) => n + d.count, 0);
  return (
    <>
      <div className="trend" aria-label={`${total} ${unit} in the period`}>
        {days.map((d) => (
          <div className="trend-col" key={d.date} title={`${formatDate(d.date)}: ${d.count}`}>
            <div className={`trend-bar${d.count ? '' : ' is-zero'}`}
              style={{ height: `${(d.count / scale) * 100}%` }} />
          </div>
        ))}
      </div>
      <div className="trend-axis muted small">
        <span>{formatDayShort(days[0].date)}</span>
        <span>{total} {unit} · busiest day {max}</span>
        <span>{formatDayShort(days[days.length - 1].date)}</span>
      </div>
    </>
  );
}

// `refreshKey`: change it to reload the numbers (e.g. after +1 Call on Home).
export default function AnalyticsStrip({ refreshKey = 0 }) {
  const [scope, setScope] = useState('me');
  const [period, setPeriod] = useState(() => initialPeriod('week'));
  const [stats, setStats] = useState(null);
  const [error, setError] = useState('');
  // Which request the numbers on screen answer; while it differs, they are fading out.
  const requestKey = `${scope}|${period.from}|${period.to}|${refreshKey}`;
  const [loadedKey, setLoadedKey] = useState(null);
  const loading = loadedKey !== requestKey;

  useEffect(() => {
    let current = true; // ignore an answer that arrives after the toggles moved on
    api.get('/stats/summary', {
      params: { scope, from: period.from, to: period.to, tz_offset: tzOffsetMinutes() },
    })
      .then((res) => { if (current) { setStats(res.data); setError(''); } })
      .catch((err) => { if (current) setError(errorMessage(err, 'Could not load the numbers.')); })
      .finally(() => { if (current) setLoadedKey(requestKey); });
    return () => { current = false; };
  }, [scope, period.from, period.to, requestKey]);

  const c = stats?.cards;
  const cards = c ? [
    ['Total leads', c.total_leads],
    ['Leads added', c.leads_added],
    ['Calls', c.calls],
    ['Follow-ups due', c.follow_ups_due],
    ['Meetings booked', c.meetings_booked],
    ['Won', c.won],
    ['Conversion', c.conversion_pct === null ? '–' : `${c.conversion_pct}%`],
  ] : [];

  return (
    <section className="stats" aria-label="Analytics">
      <div className="stats-toolbar">
        <div className="segmented" role="group" aria-label="Scope">
          {SCOPES.map(([key, label]) => (
            <button key={key} type="button" aria-pressed={scope === key}
              className={scope === key ? 'active' : undefined} onClick={() => setScope(key)}>
              {label}
            </button>
          ))}
        </div>
        <PeriodPicker value={period} onChange={setPeriod} />
      </div>

      {error && <div className="error">{error}</div>}
      {!stats && !error && <p className="hint">Loading the numbers…</p>}

      {stats && (
        <div className={loading ? 'is-loading' : undefined}>
          <div className="stat-cards">
            {cards.map(([label, value]) => (
              <div className="stat" key={label}>
                <div className="stat-value">{value}</div>
                <div className="stat-label">{label}</div>
              </div>
            ))}
          </div>

          <div className="stats-row">
            <div className="card stats-panel">
              <h3>Pipeline funnel <span className="muted small">(current status)</span></h3>
              <HBars rows={stats.funnel.map((s) => ({ label: s.status, count: s.count }))}
                colorFor={(r) => STAGE_COLORS[r.label] || 'var(--primary)'} />
            </div>
            <div className="card stats-panel">
              <h3>Leads by source <span className="muted small">(added in period)</span></h3>
              <HBars rows={stats.by_source.map((s) => ({ label: s.source, count: s.count }))}
                colorFor={() => 'var(--primary)'} />
            </div>
            <div className="card stats-panel">
              <h3>Calls per day</h3>
              <DayBars days={stats.calls_per_day} unit="calls" />
            </div>
            <div className="card stats-panel">
              <h3>Leads added per day</h3>
              <DayBars days={stats.added_per_day} unit="leads" />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
