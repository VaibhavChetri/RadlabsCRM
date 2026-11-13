// Leads.jsx
// ---------
// "All leads" (route /leads): the whole CRM as a table.
//   Search     name, company, email or phone (waits 300 ms after typing).
//   Filters    status, owner (incl. Unassigned), source, priority, date added.
//   Sort       click a column title; click again to flip the order.
//   Pages      50 leads per page, with the total count.
//   Bulk       tick leads, then set status / owner / priority, or delete (admin only, asks first).
//              The server changes them all or none, and writes history for each.
//   Export     the current filtered list (every page) as .xlsx, with notes.
//   Import     "Import file" opens the import wizard (/import).
// Filters, sort and page live in the URL, so a view can be shared or reloaded.

import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useOutletContext, useSearchParams } from 'react-router-dom';
import api from '../api';
import AddLeadForm from '../components/AddLeadForm';
import Button from '../components/Button';
import { buttonClass } from '../components/buttonClass';
import Icon from '../components/Icon';
import { saveDownload } from '../download';
import {
  DO_NOT_CALL, PRIORITIES, PRIORITY_LABELS, SOURCES, errorMessage, formatDate, formatShortDateTime,
  fullName, tzOffsetMinutes,
} from '../format';

const PAGE_SIZE = 50;
const FILTER_KEYS = ['q', 'status', 'owner', 'source', 'priority', 'added_from', 'added_to', 'import'];
const UNASSIGNED = 'unassigned'; // the API's owner filter value for "nobody"
const DEFAULT_ORDER = { added: 'desc', last_called: 'desc' }; // others: asc
const NO_SELECTION = new Set();

// URL params -> the API query string (filters, sort, page, local time zone).
function apiQuery(searchParams) {
  const params = new URLSearchParams();
  for (const key of [...FILTER_KEYS, 'sort', 'order', 'page']) {
    for (const value of searchParams.getAll(key)) {
      if (value) params.append(key, value);
    }
  }
  params.set('tz_offset', tzOffsetMinutes());
  return params.toString();
}

function SortHeader({ label, sortKey, sort, order, onSort }) {
  const active = sort === sortKey;
  return (
    <th aria-sort={active ? (order === 'asc' ? 'ascending' : 'descending') : undefined}>
      <button type="button" className={active ? 'sort-btn active' : 'sort-btn'}
        onClick={() => onSort(sortKey)}>
        {label} <span aria-hidden="true">{active ? (order === 'asc' ? '▲' : '▼') : '↕'}</span>
      </button>
    </th>
  );
}

export default function Leads() {
  const { me } = useOutletContext();
  const isAdmin = me?.role === 'admin';
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const query = apiQuery(searchParams);

  const [data, setData] = useState({ items: [], total: 0 });
  const [loadedKey, setLoadedKey] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [loadError, setLoadError] = useState('');
  const [statuses, setStatuses] = useState([]);
  const [owners, setOwners] = useState([]);
  const [showAdd, setShowAdd] = useState(false);

  const [selection, setSelection] = useState({ key: query, uuids: NO_SELECTION });
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const requestKey = `${query}#${reloadKey}`;
  const loading = loadedKey !== requestKey;

  useEffect(() => {
    let stale = false;
    api.get(`/leads?${query}&page_size=${PAGE_SIZE}`)
      .then((res) => {
        if (stale) return;
        setData(res.data);
        setLoadError('');
      })
      .catch(() => { if (!stale) setLoadError('Could not load leads. Is the backend running?'); })
      .finally(() => { if (!stale) setLoadedKey(`${query}#${reloadKey}`); });
    return () => { stale = true; };
  }, [query, reloadKey]);

  useEffect(() => {
    api.get('/statuses').then((res) => setStatuses(res.data)).catch(() => {});
    api.get('/owners').then((res) => setOwners(res.data)).catch(() => {});
  }, []);

  // Change URL params. Any change except the page itself goes back to page 1.
  const updateParams = useCallback((changes) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const [key, value] of Object.entries(changes)) {
        if (value) next.set(key, value);
        else next.delete(key);
      }
      if (!('page' in changes)) next.delete('page');
      return next;
    });
  }, [setSearchParams]);

  // Search box: typed text goes to the URL 300 ms after the last key press.
  const urlQ = searchParams.get('q') || '';
  const [searchText, setSearchText] = useState(urlQ);
  const [syncedQ, setSyncedQ] = useState(urlQ);
  if (urlQ !== syncedQ) {
    // The URL changed from outside (back button, Clear filters): follow it.
    setSyncedQ(urlQ);
    if (searchText.trim() !== urlQ) setSearchText(urlQ);
  }
  useEffect(() => {
    if (searchText.trim() === urlQ) return undefined;
    const timer = setTimeout(() => updateParams({ q: searchText.trim() }), 300);
    return () => clearTimeout(timer);
  }, [searchText, urlQ, updateParams]);

  const sort = searchParams.get('sort') || 'added';
  const order = searchParams.get('order') || DEFAULT_ORDER[sort] || 'asc';
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const hasFilters = FILTER_KEYS.some((key) => searchParams.get(key));
  const fromImport = Boolean(searchParams.get('import')); // opened from the import results

  const handleSort = (key) => {
    const nextOrder = key === sort
      ? (order === 'asc' ? 'desc' : 'asc')
      : (DEFAULT_ORDER[key] || 'asc');
    updateParams({ sort: key, order: nextOrder });
  };

  const clearFilters = () => {
    updateParams(Object.fromEntries(FILTER_KEYS.map((key) => [key, ''])));
    setSearchText('');
  };

  // ----- Selection (only for the rows on screen; a new view clears it) -----
  const selected = selection.key === query ? selection.uuids : NO_SELECTION;
  const pageUuids = data.items.map((lead) => lead.uuid);
  const allOnPage = pageUuids.length > 0 && pageUuids.every((uuid) => selected.has(uuid));

  const setSelected = (uuids) => setSelection({ key: query, uuids });
  const toggle = (uuid) => {
    const next = new Set(selected);
    if (next.has(uuid)) next.delete(uuid);
    else next.add(uuid);
    setSelected(next);
  };
  const toggleAll = () => setSelected(allOnPage ? NO_SELECTION : new Set(pageUuids));

  const reload = () => setReloadKey((k) => k + 1);

  // ----- Bulk actions -----
  const runBulk = async (body, doneText) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await api.post('/leads/bulk', { uuids: [...selected], ...body });
      const n = res.data.count;
      setNotice(`${n} ${n === 1 ? 'lead' : 'leads'} ${doneText}.`);
      setSelected(NO_SELECTION);
      reload();
    } catch (err) {
      setError(errorMessage(err, 'Could not update the leads. Nothing was changed.'));
    } finally {
      setBusy(false);
    }
  };

  const bulkSet = (field, value, doneText) => {
    if (!value) return;
    runBulk({ action: 'update', changes: { [field]: value === UNASSIGNED ? null : value } }, doneText);
  };

  const bulkDelete = () => {
    const n = selected.size;
    const ok = window.confirm(
      `Delete ${n} ${n === 1 ? 'lead' : 'leads'}? Their calls, notes and history go too. This cannot be undone.`,
    );
    if (ok) runBulk({ action: 'delete' }, 'deleted');
  };

  // ----- Export -----
  const handleExport = async () => {
    setExporting(true);
    setError('');
    try {
      const res = await api.get(`/leads/export?${query}`, { responseType: 'blob' });
      saveDownload(res, 'radlabs-leads.xlsx');
    } catch {
      setError('Could not export. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  const first = data.total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const last = Math.min(page * PAGE_SIZE, data.total);

  return (
    <>
      <div className="lead-head">
        <div>
          <h1>All leads</h1>
          <p className="subtitle">
            {data.total} {data.total === 1 ? 'lead' : 'leads'}
            {fromImport ? ' added by your import'
              : hasFilters ? (data.total === 1 ? ' matches' : ' match') : ' in the CRM'}
            {fromImport && (
              <> · <Button variant="link" onClick={() => updateParams({ import: '' })}>Show all leads</Button></>
            )}
          </p>
        </div>
        <div className="actions">
          <Button variant="outline" icon="download" onClick={handleExport}
            loading={exporting} disabled={data.total === 0}>
            {exporting ? 'Exporting…' : 'Export to Excel'}
          </Button>
          <Link className={buttonClass({ variant: 'outline' })} to="/import">
            <Icon name="upload" />Import file
          </Link>
          <Button variant={showAdd ? 'outline' : 'primary'} icon={showAdd ? 'x' : 'plus'}
            onClick={() => setShowAdd((v) => !v)}>
            {showAdd ? 'Close' : 'Add lead'}
          </Button>
        </div>
      </div>

      {showAdd && <AddLeadForm onAdded={reload} onOpenExisting={(uuid) => navigate(`/leads/${uuid}`)} />}

      <div className="card">
        <div className="filters">
          <label className="filter-search">
            Search
            <input type="search" placeholder="Name, company, email or phone"
              value={searchText} onChange={(e) => setSearchText(e.target.value)} />
          </label>
          <label>
            Status
            <select value={searchParams.get('status') || ''}
              onChange={(e) => updateParams({ status: e.target.value })}>
              <option value="">All</option>
              {statuses.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
            </select>
          </label>
          <label>
            Owner
            <select value={searchParams.get('owner') || ''}
              onChange={(e) => updateParams({ owner: e.target.value })}>
              <option value="">Anyone</option>
              <option value={UNASSIGNED}>Unassigned</option>
              {owners.map((o) => <option key={o.uuid} value={o.uuid}>{o.name}</option>)}
            </select>
          </label>
          <label>
            Source
            <select value={searchParams.get('source') || ''}
              onChange={(e) => updateParams({ source: e.target.value })}>
              <option value="">All</option>
              {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label>
            Priority
            <select value={searchParams.get('priority') || ''}
              onChange={(e) => updateParams({ priority: e.target.value })}>
              <option value="">All</option>
              {PRIORITIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label>
            Added from
            <input type="date" value={searchParams.get('added_from') || ''}
              onChange={(e) => updateParams({ added_from: e.target.value })} />
          </label>
          <label>
            Added to
            <input type="date" value={searchParams.get('added_to') || ''}
              onChange={(e) => updateParams({ added_to: e.target.value })} />
          </label>
        </div>
        {hasFilters && (
          <Button variant="link" onClick={clearFilters}>Clear filters</Button>
        )}
      </div>

      {notice && <div className="notice">{notice}</div>}
      {error && <div className="error">{error}</div>}

      {selected.size > 0 && (
        <div className="bulk-bar">
          <strong>{selected.size} selected</strong>
          <select className="compact" value="" disabled={busy}
            onChange={(e) => bulkSet('status', e.target.value, `moved to ${e.target.value}`)}>
            <option value="">Set status…</option>
            {statuses.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
          <select className="compact" value="" disabled={busy}
            onChange={(e) => bulkSet('owner_uuid', e.target.value, 'reassigned')}>
            <option value="">Set owner…</option>
            <option value={UNASSIGNED}>Unassigned</option>
            {owners.map((o) => <option key={o.uuid} value={o.uuid}>{o.name}</option>)}
          </select>
          <select className="compact" value="" disabled={busy}
            onChange={(e) => bulkSet('priority', e.target.value, `set to ${PRIORITY_LABELS[e.target.value]}`)}>
            <option value="">Set priority…</option>
            {PRIORITIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          {isAdmin && (
            <Button variant="danger" size="sm" icon="trash" disabled={busy} onClick={bulkDelete}>
              Delete
            </Button>
          )}
          <Button variant="link" disabled={busy} onClick={() => setSelected(NO_SELECTION)}>
            Clear selection
          </Button>
        </div>
      )}

      <div className="card">
        {loadError && <div className="error">{loadError}</div>}
        {!loadError && loadedKey === null && <p className="hint">Loading leads…</p>}
        {!loadError && loadedKey !== null && data.items.length === 0 && (
          <p className="hint">
            {hasFilters ? 'No leads match these filters.' : 'No leads yet. Use "+ Add lead" to add your first one.'}
          </p>
        )}

        {!loadError && data.items.length > 0 && (
          <div className={loading ? 'table-wrap is-loading' : 'table-wrap'}>
            <table className="leads-table">
              <thead>
                <tr>
                  <th className="check-col">
                    <input type="checkbox" aria-label="Select all on this page"
                      checked={allOnPage} onChange={toggleAll} />
                  </th>
                  <th>Name / email</th>
                  <SortHeader label="Company" sortKey="company" sort={sort} order={order} onSort={handleSort} />
                  <th>Phone</th>
                  <th>Status</th>
                  <SortHeader label="Priority" sortKey="priority" sort={sort} order={order} onSort={handleSort} />
                  <th>Owner</th>
                  <th>Calls</th>
                  <SortHeader label="Last called" sortKey="last_called" sort={sort} order={order} onSort={handleSort} />
                  <SortHeader label="Follow-up" sortKey="follow_up" sort={sort} order={order} onSort={handleSort} />
                  <SortHeader label="Added to CRM" sortKey="added" sort={sort} order={order} onSort={handleSort} />
                </tr>
              </thead>
              <tbody>
                {data.items.map((lead) => (
                  <tr key={lead.uuid} className={selected.has(lead.uuid) ? 'row-selected' : undefined}>
                    <td className="check-col">
                      <input type="checkbox" aria-label={`Select ${fullName(lead)}`}
                        checked={selected.has(lead.uuid)} onChange={() => toggle(lead.uuid)} />
                    </td>
                    <td>
                      <Link to={`/leads/${lead.uuid}`}>{fullName(lead) || 'Unnamed lead'}</Link>
                      {lead.email && <div className="muted small">{lead.email}</div>}
                    </td>
                    <td>{lead.company}</td>
                    <td>{lead.phone}</td>
                    <td>
                      <span className={lead.status === DO_NOT_CALL ? 'badge danger' : 'badge'}>
                        {lead.status}
                      </span>
                    </td>
                    <td><span className={`badge priority-${lead.priority}`}>{PRIORITY_LABELS[lead.priority]}</span></td>
                    <td>{lead.owner || <span className="muted">Unassigned</span>}</td>
                    <td>{lead.call_attempts}</td>
                    <td>{lead.last_called_at ? formatShortDateTime(lead.last_called_at) : <span className="muted">Never</span>}</td>
                    <td>{lead.next_follow_up ? formatDate(lead.next_follow_up) : <span className="muted">None</span>}</td>
                    <td>
                      {formatShortDateTime(lead.created_at)}
                      {lead.created_by && <div className="muted small">by {lead.created_by}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loadError && data.total > PAGE_SIZE && (
          <div className="pager">
            <span className="muted">Showing {first}–{last} of {data.total}</span>
            <span className="input-row">
              <Button variant="outline" size="sm" icon="chevronLeft" disabled={page <= 1}
                onClick={() => updateParams({ page: String(page - 1) })}>
                Previous
              </Button>
              <span className="muted">Page {page} of {pages}</span>
              <Button variant="outline" size="sm" iconAfter="chevronRight" disabled={page >= pages}
                onClick={() => updateParams({ page: String(page + 1) })}>
                Next
              </Button>
            </span>
          </div>
        )}
      </div>
    </>
  );
}
