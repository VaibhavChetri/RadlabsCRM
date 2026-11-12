// Import.jsx
// ----------
// Import leads from a file (route /import). Three steps:
//   1. Choose     an .xlsx or .csv file (max 5 MB, 5,000 rows).
//   2. Map        Source, Assign to, and a CRM field (or Skip) for each column.
//                 The mapping is suggested from the headers; a saved preset (e.g. the
//                 built-in Apollo one) maps a known file with no changes. The first
//                 5 rows are shown as they will look in the CRM.
//   3. Report     added / updated / skipped with the reason, downloadable as .xlsx.
// People already in the CRM (same email, phone or LinkedIn) are never added twice:
// only their empty fields are filled. Status, owner, notes and calls never change.
// Below the wizard: the import history (who, when, file, source, counts).

import { useCallback, useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import api from '../api';
import { saveDownload } from '../download';
import {
  IMPORT_FIELDS, IMPORT_FIELD_LABELS, SOURCES, errorMessage, formatDateTime,
} from '../format';

const MAX_BYTES = 5 * 1024 * 1024;
const CONTACT_FIELDS = ['email', 'phone', 'linkedin_url'];
const REPORT_ROWS_SHOWN = 200;
const PREVIEW_DELAY_MS = 400;

// Columns of the CRM preview table, in field order. A full name shows as first + last.
function previewColumns(mapping) {
  const used = new Set(Object.values(mapping).filter(Boolean));
  if (used.has('full_name')) { used.add('first_name'); used.add('last_name'); }
  return IMPORT_FIELDS.map(([key]) => key).filter((key) => key !== 'full_name' && used.has(key));
}

function uploadForm(file, fields = {}) {
  const form = new FormData();
  form.append('file', file);
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  return form;
}

// ---------- Step 1: choose a file ----------
function ChooseFile({ onPreview }) {
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleFile = async (e) => {
    const file = e.target.files[0];
    e.target.value = ''; // choosing the same file again still fires onChange
    if (!file) return;
    setError('');
    if (!/\.(xlsx|csv)$/i.test(file.name)) {
      setError('Only .xlsx and .csv files can be imported.');
      return;
    }
    if (file.size > MAX_BYTES) {
      setError('The file is larger than 5 MB. Split it and import each part.');
      return;
    }
    setLoading(true);
    try {
      const res = await api.post('/imports/preview', uploadForm(file));
      onPreview(file, res.data);
    } catch (err) {
      setError(errorMessage(err, 'Could not read the file. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h2>1. Choose a file</h2>
      <p className="muted">
        An .xlsx or .csv file with one lead per row and column names in the first row
        (max 5 MB, 5,000 rows). Apollo exports map automatically.
      </p>
      <label className="file-pick">
        {loading ? 'Reading the file…' : 'Choose file'}
        <input type="file" accept=".xlsx,.csv" onChange={handleFile} disabled={loading} />
      </label>
      {error && <div className="error">{error}</div>}
    </div>
  );
}

// ---------- Step 2: map columns, preview, import ----------
function MapColumns({ file, preview, me, onDone, onCancel }) {
  const [mapping, setMapping] = useState(preview.mapping);
  const [mappedRows, setMappedRows] = useState(preview.mapped_rows);
  const [previewKey, setPreviewKey] = useState(JSON.stringify(preview.mapping));
  const [source, setSource] = useState(preview.preset === 'Apollo' ? 'Apollo' : 'Other');
  const [assignTo, setAssignTo] = useState('');
  const [owners, setOwners] = useState([]);
  const [presets, setPresets] = useState([]);
  const [presetName, setPresetName] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [importing, setImporting] = useState(false);

  const loadPresets = useCallback(() => {
    api.get('/imports/presets').then((res) => setPresets(res.data)).catch(() => {});
  }, []);
  useEffect(() => {
    api.get('/owners').then((res) => setOwners(res.data)).catch(() => {});
    loadPresets();
  }, [loadPresets]);

  // The CRM preview follows the mapping (asked from the server a moment after a change).
  const mappingKey = JSON.stringify(mapping);
  useEffect(() => {
    if (mappingKey === previewKey) return undefined;
    let stale = false;
    const timer = setTimeout(() => {
      api.post('/imports/preview', uploadForm(file, { mapping: mappingKey }))
        .then((res) => { if (!stale) { setMappedRows(res.data.mapped_rows); setPreviewKey(mappingKey); } })
        .catch(() => {});
    }, PREVIEW_DELAY_MS);
    return () => { stale = true; clearTimeout(timer); };
  }, [file, mappingKey, previewKey]);

  const effectiveAssign = assignTo || me?.uuid || 'unassigned';
  const hasContact = Object.values(mapping).some((f) => CONTACT_FIELDS.includes(f));
  const columns = previewColumns(mapping);

  const setField = (header, field) => setMapping({ ...mapping, [header]: field || null });

  const applyPreset = (name) => {
    const preset = presets.find((p) => p.name === name);
    if (!preset) return;
    const byHeader = Object.fromEntries(
      Object.entries(preset.mapping).map(([h, f]) => [h.trim().toLowerCase(), f]));
    setMapping(Object.fromEntries(preview.headers.map((h) => {
      const key = h.trim().toLowerCase();
      return [h, key in byHeader ? byHeader[key] : mapping[h]];
    })));
    setNotice(`Applied the ${preset.name} preset.`);
  };

  const savePreset = async () => {
    setError('');
    setNotice('');
    try {
      await api.post('/imports/presets', { name: presetName, mapping });
      setNotice(`Saved preset "${presetName.trim()}". Files with these columns will map automatically.`);
      setPresetName('');
      loadPresets();
    } catch (err) {
      setError(errorMessage(err, 'Could not save the preset.'));
    }
  };

  const runImport = async () => {
    setError('');
    setImporting(true);
    try {
      const res = await api.post('/imports', uploadForm(file, {
        mapping: mappingKey, source, assign_to: effectiveAssign,
      }));
      onDone(res.data);
    } catch (err) {
      setError(errorMessage(err, 'The import failed. Nothing was imported.'));
    } finally {
      setImporting(false);
    }
  };

  return (
    <>
      <div className="card">
        <div className="card-head">
          <h2>2. Map columns</h2>
          <button type="button" className="link-btn" onClick={onCancel}>Choose another file</button>
        </div>
        <p className="muted">
          <strong>{preview.file_name}</strong> · {preview.row_count} rows
          {preview.preset && <> · <span className="badge">Matched preset: {preview.preset}</span></>}
        </p>

        <div className="form-grid">
          <label>
            Source
            <select value={source} onChange={(e) => setSource(e.target.value)}>
              {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label>
            Assign new leads to
            <select value={effectiveAssign} onChange={(e) => setAssignTo(e.target.value)}>
              {owners.map((o) => (
                <option key={o.uuid} value={o.uuid}>{o.uuid === me?.uuid ? `Me (${o.name})` : o.name}</option>
              ))}
              <option value="split">Split evenly across the team</option>
              <option value="unassigned">Unassigned</option>
            </select>
          </label>
          <label>
            Apply a preset
            <select value="" onChange={(e) => applyPreset(e.target.value)}>
              <option value="">Choose…</option>
              {presets.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
            </select>
          </label>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>File column</th><th>Sample values</th><th>CRM field</th></tr>
            </thead>
            <tbody>
              {preview.headers.map((header, i) => (
                <tr key={header} className={mapping[header] ? undefined : 'row-skipped'}>
                  <td><strong>{header}</strong></td>
                  <td className="muted sample-cell">
                    {preview.sample_rows.map((row) => row[i]).filter(Boolean).slice(0, 2).join(' · ')}
                  </td>
                  <td>
                    <select className="compact" value={mapping[header] || ''}
                      onChange={(e) => setField(header, e.target.value)}>
                      <option value="">Skip</option>
                      {IMPORT_FIELDS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="input-row preset-save">
          <input placeholder="Save this mapping as a preset, e.g. Expo sheet" value={presetName}
            maxLength={100} onChange={(e) => setPresetName(e.target.value)} />
          <button type="button" className="secondary" onClick={savePreset}
            disabled={!presetName.trim()}>Save preset</button>
        </div>
        {notice && <div className="notice">{notice}</div>}
      </div>

      <div className="card">
        <h2>Preview: first {mappedRows.length} rows as they will look in the CRM</h2>
        {columns.length === 0 ? (
          <p className="muted">No columns are mapped yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>{columns.map((key) => <th key={key}>{IMPORT_FIELD_LABELS[key]}</th>)}</tr>
              </thead>
              <tbody>
                {mappedRows.map((row, i) => (
                  <tr key={i}>
                    {columns.map((key) => <td key={key}>{row[key] || <span className="muted">—</span>}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted">
          Rows with no email, phone or LinkedIn URL are skipped. People already in the CRM only
          get their empty fields filled; their status, owner, notes and calls never change.
        </p>
        {!hasContact && <div className="error">Map at least one column to Email, Phone or LinkedIn URL.</div>}
        {error && <div className="error">{error}</div>}
        <button type="button" className="inline" onClick={runImport} disabled={!hasContact || importing}>
          {importing ? `Importing ${preview.row_count} rows…` : `Import ${preview.row_count} rows`}
        </button>
      </div>
    </>
  );
}

// ---------- Step 3: report ----------
function Report({ report, onAgain }) {
  const [error, setError] = useState('');
  const notAdded = report.rows.filter((r) => r.result !== 'added');

  const download = async () => {
    setError('');
    try {
      const res = await api.post('/imports/report', report, { responseType: 'blob' });
      saveDownload(res, 'import-report.xlsx');
    } catch {
      setError('Could not download the report. Please try again.');
    }
  };

  return (
    <div className="card">
      <h2>3. Import report</h2>
      <div className="stat-cards">
        <div className="stat"><div className="stat-value">{report.added}</div><div className="stat-label">Added</div></div>
        <div className="stat"><div className="stat-value">{report.updated}</div><div className="stat-label">Updated (empty fields filled)</div></div>
        <div className="stat"><div className="stat-value">{report.skipped}</div><div className="stat-label">Skipped</div></div>
      </div>

      {notAdded.length === 0 ? (
        <p className="muted">Every row was added as a new lead.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Row</th><th>Result</th><th>Reason</th><th>Row data</th></tr></thead>
            <tbody>
              {notAdded.slice(0, REPORT_ROWS_SHOWN).map((r) => (
                <tr key={r.row}>
                  <td>{r.row}</td>
                  <td><span className={r.result === 'skipped' ? 'badge danger' : 'badge'}>{r.result}</span></td>
                  <td>{r.reason}</td>
                  <td className="muted sample-cell">{r.values.filter(Boolean).slice(0, 4).join(' · ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {notAdded.length > REPORT_ROWS_SHOWN && (
            <p className="muted">Showing {REPORT_ROWS_SHOWN} of {notAdded.length}. Download the report for all rows.</p>
          )}
        </div>
      )}
      {error && <div className="error">{error}</div>}
      <div className="actions">
        <button type="button" className="secondary" onClick={download}>Download report (.xlsx)</button>
        <button type="button" className="inline" onClick={onAgain}>Import another file</button>
        <Link to="/leads?sort=added">View all leads</Link>
      </div>
    </div>
  );
}

// ---------- History ----------
function History({ reloadKey }) {
  const [history, setHistory] = useState(null);

  useEffect(() => {
    api.get('/imports').then((res) => setHistory(res.data)).catch(() => setHistory([]));
  }, [reloadKey]);

  return (
    <div className="card">
      <h2>Import history</h2>
      {history === null ? (
        <p className="muted">Loading…</p>
      ) : history.length === 0 ? (
        <p className="muted">No imports yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>When</th><th>Who</th><th>File</th><th>Source</th><th>Added</th><th>Updated</th><th>Skipped</th></tr>
            </thead>
            <tbody>
              {history.map((h, i) => (
                <tr key={i}>
                  <td>{formatDateTime(h.created_at)}</td>
                  <td>{h.user}</td>
                  <td>{h.file_name}</td>
                  <td>{h.source}</td>
                  <td>{h.added}</td>
                  <td>{h.updated}</td>
                  <td>{h.skipped}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function Import() {
  const { me } = useOutletContext();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [report, setReport] = useState(null);
  const [historyKey, setHistoryKey] = useState(0);

  const startAgain = () => { setFile(null); setPreview(null); setReport(null); };

  return (
    <>
      <h1>Import leads</h1>
      <p className="subtitle">From Apollo, LinkedIn, events or any spreadsheet.</p>

      {report ? (
        <Report report={report} onAgain={startAgain} />
      ) : preview ? (
        <MapColumns key={preview.file_name + preview.row_count} file={file} preview={preview} me={me}
          onCancel={startAgain}
          onDone={(result) => { setReport(result); setHistoryKey((k) => k + 1); }} />
      ) : (
        <ChooseFile onPreview={(chosen, data) => { setFile(chosen); setPreview(data); }} />
      )}

      <History reloadKey={historyKey} />
    </>
  );
}
