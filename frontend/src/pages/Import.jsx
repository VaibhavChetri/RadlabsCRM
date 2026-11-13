// Import.jsx
// ----------
// Import leads from a file (route /import). Three steps, shown in a step bar:
//   1. Choose     an .xlsx or .csv file (max 5 MB, 5,000 rows).
//   2. Match      Source, Assign to, and a CRM field (or Skip) for each column.
//                 The mapping is suggested from the headers; a saved preset (e.g. the
//                 built-in Apollo one) maps a known file with no changes. The first
//                 5 rows are shown as they will look in the CRM.
//   3. Results    the outcome and "View new leads" (only the leads this import added),
//                 rows to fix (with a download of just those rows), then folded lists:
//                 added / updated (fields filled) / skipped.
// People already in the CRM (same email, phone or LinkedIn) are never added twice:
// only their empty fields are filled. Status, owner, notes and calls never change.
// Below the wizard: the import history (who, when, file, source, counts).

import { useCallback, useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import api from '../api';
import { saveDownload } from '../download';
import Button from '../components/Button';
import { buttonClass } from '../components/buttonClass';
import Icon from '../components/Icon';
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

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

const STEPS = ['Choose file', 'Match columns', 'See results'];

function Steps({ current }) {
  return (
    <ol className="steps" aria-label="Import steps">
      {STEPS.map((label, i) => {
        const n = i + 1;
        const state = n < current ? 'done' : n === current ? 'current' : 'todo';
        return (
          <li key={label} className={`step step-${state}`} aria-current={state === 'current' ? 'step' : undefined}>
            <span className="step-dot">{state === 'done' ? <Icon name="check" /> : n}</span>
            <span className="step-label">{label}</span>
          </li>
        );
      })}
    </ol>
  );
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
      <h2>Choose a file</h2>
      <p className="muted">
        An .xlsx or .csv file with one lead per row and column names in the first row
        (max 5 MB, 5,000 rows). Apollo exports map automatically.
      </p>
      <label className={buttonClass({ className: 'file-pick' })}>
        {loading ? <span className="btn-spinner" aria-hidden="true" /> : <Icon name="fileUp" />}
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
      const ownerLabel = effectiveAssign === 'split' ? 'split evenly across the team'
        : effectiveAssign === 'unassigned' ? 'nobody (Unassigned)'
          : effectiveAssign === me?.uuid ? 'you'
            : owners.find((o) => o.uuid === effectiveAssign)?.name || 'the chosen person';
      onDone(res.data, { source, ownerLabel, fileName: preview.file_name });
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
          <h2>Match columns</h2>
          <Button variant="link" onClick={onCancel}>Choose another file</Button>
        </div>
        <p className="muted">
          <strong>{preview.file_name}</strong> · {plural(preview.row_count, 'row')}
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
              {/* Until the team list loads, still show the real default (me). */}
              {!owners.length && me && <option value={me.uuid}>Me ({me.name})</option>}
              {owners.map((o) => (
                <option key={o.uuid} value={o.uuid}>{o.uuid === me?.uuid ? `Me (${o.name})` : o.name}</option>
              ))}
              <option value="split">Split evenly across the team</option>
              <option value="unassigned">Unassigned</option>
            </select>
          </label>
          <label>
            Apply a saved format
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
          <input placeholder="Save this mapping format as preset, e.g. Expo Sheet" value={presetName}
            maxLength={100} onChange={(e) => setPresetName(e.target.value)} />
          <Button variant="outline" icon="save" onClick={savePreset}
            disabled={!presetName.trim()}>Save preset</Button>
        </div>
        {notice && <div className="notice">{notice}</div>}
      </div>

      <div className="card">
        <h2>Preview: how the first {plural(mappedRows.length, 'row')} will look in the CRM</h2>
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
        <Button icon="upload" onClick={runImport} loading={importing} disabled={!hasContact}>
          {importing ? `Importing ${plural(preview.row_count, 'row')}…` : `Import ${plural(preview.row_count, 'row')}`}
        </Button>
      </div>
    </>
  );
}

// ---------- Step 3: results ----------
// Short reason for a skipped row. needsFix: the user must change the row to import it.
function explain(row) {
  if (row.reason === 'no contact info') return { needsFix: true, problem: 'No email, phone or LinkedIn' };
  if (row.reason === 'no name') return { needsFix: true, problem: 'No name' };
  const dup = /^duplicate of row (\d+)/.exec(row.reason);
  if (dup) return { needsFix: false, problem: `Same person as row ${dup[1]}` };
  if (row.reason === 'already in CRM, nothing new') return { needsFix: false, problem: 'Already in the CRM, nothing new' };
  return { needsFix: row.result === 'skipped', problem: row.reason };
}

// The row's other values, e.g. "sneha@brightpath.in · 98200 11223" (name left out:
// it has its own column). A re-uploaded "rows to fix" file starts with Row / Result /
// Reason: not shown.
const REPORT_COLUMNS = ['Row', 'Result', 'Reason'];
function rowDetails(headers, values, name, limit = 3) {
  const skip = REPORT_COLUMNS.every((c, i) => headers[i] === c) ? REPORT_COLUMNS.length : 0;
  const nameParts = new Set(name.toLowerCase().split(' ').concat(name.toLowerCase()));
  return values.slice(skip).filter((v) => v && !nameParts.has(v.trim().toLowerCase()))
    .slice(0, limit).join(' · ');
}

// One line per file row: row number, name, what happened.
function ResultRows({ rows, detail }) {
  return (
    <ul className="result-rows">
      {rows.slice(0, REPORT_ROWS_SHOWN).map((r) => (
        <li key={r.row}>
          <span className="result-rownum">Row {r.row}</span>
          <span className="result-name">{r.name || <span className="muted" aria-label="No name">—</span>}</span>
          <span className="result-detail">{detail(r)}</span>
        </li>
      ))}
      {rows.length > REPORT_ROWS_SHOWN && (
        <li className="result-more">{rows.length - REPORT_ROWS_SHOWN} more in the full report</li>
      )}
    </ul>
  );
}

function Outcome({ label, rows, detail }) {
  if (!rows.length) return null;
  return (
    <details className="result-outcome">
      <summary>{label} <span className="result-count">{rows.length}</span></summary>
      <ResultRows rows={rows} detail={detail} />
    </details>
  );
}

function Results({ report, context, onAgain }) {
  const [error, setError] = useState('');
  const rows = report.rows.map((r) => ({ ...r, ...explain(r) }));
  const added = rows.filter((r) => r.result === 'added');
  const updated = rows.filter((r) => r.result === 'updated');
  const toFix = rows.filter((r) => r.result === 'skipped' && r.needsFix);
  const skipped = rows.filter((r) => r.result === 'skipped' && !r.needsFix);

  const headline = added.length ? `${plural(added.length, 'new lead')} added`
    : updated.length ? `${plural(updated.length, 'lead')} updated, no new leads`
      : 'No leads added';
  const facts = [context.fileName, `Source: ${context.source}`,
    added.length > 0 && `Owner: ${context.ownerLabel}`].filter(Boolean).join(' · ');

  const newLeadsUrl = `/leads?import=${report.import_uuid}`; // only the leads this import added

  const download = async (onlyToFix) => {
    setError('');
    try {
      const body = onlyToFix ? { ...report, rows: report.rows.filter((r) => toFix.some((f) => f.row === r.row)) } : report;
      const res = await api.post('/imports/report', body, { responseType: 'blob' });
      saveDownload(res, 'import-report.xlsx', onlyToFix ? 'rows-to-fix.xlsx' : undefined);
    } catch {
      setError('Could not download the file. Please try again.');
    }
  };

  return (
    <div className="card">
      <div className="result-head" role="status">
        <div>
          <h2>{headline}</h2>
          <p className="muted">{facts}</p>
        </div>
        <div className="actions">
          {added.length > 0 && (
            <Link className={buttonClass()} to={newLeadsUrl}>
              View {added.length === 1 ? 'new lead' : `${added.length} new leads`}<Icon name="chevronRight" />
            </Link>
          )}
          <Button variant="outline" icon="fileUp" onClick={onAgain}>Import another file</Button>
        </div>
      </div>

      {toFix.length > 0 && (
        <section className="result-fix" aria-labelledby="result-fix-title">
          <div className="result-fix-head">
            <h3 id="result-fix-title"><Icon name="alert" />{plural(toFix.length, 'row')} not added</h3>
            <Button size="sm" variant={added.length ? 'outline' : 'primary'} icon="download"
              onClick={() => download(true)}>
              Download to fix
            </Button>
          </div>
          <ResultRows rows={toFix} detail={(r) => r.problem} />
        </section>
      )}

      <div className="result-outcomes">
        <Outcome label="Added" rows={added} detail={(r) => rowDetails(report.headers, r.values, r.name)} />
        <Outcome label="Updated" rows={updated}
          detail={(r) => `Filled in: ${r.filled.map((f) => IMPORT_FIELD_LABELS[f] || f).join(', ') || '—'}`} />
        <Outcome label="Skipped" rows={skipped} detail={(r) => r.problem} />
      </div>

      {error && <div className="error">{error}</div>}
      <div className="result-foot">
        <Button variant="link" icon="download" onClick={() => download(false)}>
          Download full report
        </Button>
        {added.length > 0 ? (
          <Link className={buttonClass({ variant: 'outline' })} to={newLeadsUrl}>
            View {added.length === 1 ? 'new lead' : `${added.length} new leads`}<Icon name="chevronRight" />
          </Link>
        ) : (
          <Link className={buttonClass({ variant: 'outline' })} to="/leads">
            Go to All leads<Icon name="chevronRight" />
          </Link>
        )}
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
      <h2>Past imports</h2>
      {history === null ? (
        <p className="muted">Loading…</p>
      ) : history.length === 0 ? (
        <p className="muted">No imports yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>When</th><th>Who</th><th>File</th><th>Source</th><th>New leads</th><th>Updated</th><th>Not added</th></tr>
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
  const [context, setContext] = useState(null);
  const [historyKey, setHistoryKey] = useState(0);

  const startAgain = () => { setFile(null); setPreview(null); setReport(null); setContext(null); };
  const step = report ? 3 : preview ? 2 : 1;

  return (
    <>
      <h1>Import leads</h1>
      <p className="subtitle">From Apollo, LinkedIn, events or any spreadsheet.</p>
      <Steps current={step} />

      {report ? (
        <Results report={report} context={context} onAgain={startAgain} />
      ) : preview ? (
        <MapColumns key={preview.file_name + preview.row_count} file={file} preview={preview} me={me}
          onCancel={startAgain}
          onDone={(result, ctx) => { setReport(result); setContext(ctx); setHistoryKey((k) => k + 1); }} />
      ) : (
        <ChooseFile onPreview={(chosen, data) => { setFile(chosen); setPreview(data); }} />
      )}

      <History reloadKey={historyKey} />
    </>
  );
}
