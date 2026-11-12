// StatsOverview.jsx
// -----------------
// The dashboard's analytics block: stat cards + a pipeline funnel + a 14-day
// trend. All numbers come from GET /leads/stats (already scoped to this client).
// Charts are plain CSS bars — no charting library (ponytail: a dependency would
// be overkill for two simple bar visuals).

import { useEffect, useState } from 'react';
import api from '../api';

export default function StatsOverview() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    // Errors (incl. 401) are already handled by Dashboard's leads fetch, so
    // here we just stay hidden if stats can't load.
    api.get('/leads/stats').then((res) => setStats(res.data)).catch(() => {});
  }, []);

  if (!stats) return null;

  const { total, by_status, conversion_rate, last_7_days, trend } = stats;
  const funnelMax = Math.max(by_status.new, by_status.contacted, by_status.closed, 1);
  const trendMax = Math.max(...trend.map((d) => d.count), 1);

  const cards = [
    { label: 'Total leads', value: total },
    { label: 'New', value: by_status.new },
    { label: 'Contacted', value: by_status.contacted },
    { label: 'Closed', value: by_status.closed },
    { label: 'Conversion', value: `${conversion_rate}%` },
    { label: 'Last 7 days', value: last_7_days },
  ];

  const funnel = [
    ['New', by_status.new, '#2563eb'],
    ['Contacted', by_status.contacted, '#d97706'],
    ['Closed', by_status.closed, '#16a34a'],
  ];

  return (
    <div className="stats">
      <div className="stat-cards">
        {cards.map((c) => (
          <div className="stat" key={c.label}>
            <div className="stat-value">{c.value}</div>
            <div className="stat-label">{c.label}</div>
          </div>
        ))}
      </div>

      <div className="stats-row">
        <div className="card stats-panel">
          <h3>Pipeline funnel</h3>
          {funnel.map(([label, count, color]) => (
            <div className="funnel-row" key={label}>
              <span className="funnel-label">{label}</span>
              <div className="funnel-track">
                <div
                  className="funnel-bar"
                  style={{ width: `${(count / funnelMax) * 100}%`, background: color }}
                />
              </div>
              <span className="funnel-count">{count}</span>
            </div>
          ))}
        </div>

        <div className="card stats-panel">
          <h3>Last 14 days</h3>
          <div className="trend">
            {trend.map((d) => (
              <div className="trend-col" key={d.date} title={`${d.date}: ${d.count}`}>
                <div
                  className="trend-bar"
                  style={{ height: `${(d.count / trendMax) * 100}%` }}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
