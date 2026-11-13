// format.js
// ---------
// Small display helpers shared by the lead screens.
// API times are UTC with an offset; the browser shows them in local time.

export function formatDateTime(value) {
  if (!value) return '';
  const d = new Date(value);
  return isNaN(d) ? value : d.toLocaleString(undefined, {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

// Short form for tables: "13 Nov, 15:02" ("13 Nov 2025, 15:02" for another year).
export function formatShortDateTime(value, now = new Date()) {
  if (!value) return '';
  const d = new Date(value);
  if (isNaN(d)) return value;
  const sameYear = d.getFullYear() === now.getFullYear();
  return d.toLocaleString(undefined, {
    day: 'numeric', month: 'short', ...(sameYear ? {} : { year: 'numeric' }),
    hour: '2-digit', minute: '2-digit',
  });
}

// A plain "YYYY-MM-DD" date (e.g. a follow-up) -> "12 Nov 2026".
// Parsed as a local date, so it never shifts by a day.
export function formatDate(value) {
  if (!value) return '';
  const [y, m, d] = value.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    day: '2-digit', month: 'short', year: 'numeric',
  });
}

// Today in the browser's time zone as "YYYY-MM-DD" (what the API expects).
export function localDateISO(now = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function fullName(lead) {
  return [lead.first_name, lead.last_name].filter(Boolean).join(' ');
}

// API error -> one readable line.
export function errorMessage(err, fallback = 'Something went wrong. Please try again.') {
  const detail = err.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg.replace(/^Value error, /, '')).join('. ');
  }
  if (typeof detail === 'string') return detail;
  return fallback;
}

// "acme.com" -> "https://acme.com" so links open the real site.
export function externalUrl(value) {
  if (!value) return '';
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}

// wa.me needs the full number in digits. A bare 10-digit number is
// taken as Indian (+91), since the team calls from India.
export function whatsappUrl(phone) {
  let digits = (phone || '').replace(/\D/g, '');
  if (digits.length === 10) digits = `91${digits}`;
  return digits ? `https://wa.me/${digits}` : '';
}

export const DO_NOT_CALL = 'Do not call';

// Fixed lists, same as the backend (models.py).
export const SOURCES = ['Apollo', 'LinkedIn', 'Referral', 'Event', 'Cold list', 'Other'];
export const PRIORITIES = [['hot', 'Hot'], ['warm', 'Warm'], ['cold', 'Cold']];
export const PRIORITY_LABELS = Object.fromEntries(PRIORITIES);

// The browser's local time minus UTC, in minutes (IST = 330). The API uses it
// to read date filters as local dates and to write local times in exports.
export function tzOffsetMinutes(now = new Date()) {
  return -now.getTimezoneOffset();
}

// CRM fields a file column can be imported into (same keys as the backend).
export const IMPORT_FIELDS = [
  ['full_name', 'Full name (split into first + last)'],
  ['first_name', 'First name'],
  ['last_name', 'Last name'],
  ['job_title', 'Job title'],
  ['email', 'Email'],
  ['phone', 'Phone'],
  ['phone_2', 'Second phone'],
  ['linkedin_url', 'LinkedIn URL'],
  ['company', 'Company'],
  ['website', 'Website'],
  ['industry', 'Industry'],
  ['company_size', 'Company size'],
  ['city', 'City'],
  ['country', 'Country'],
];
export const IMPORT_FIELD_LABELS = Object.fromEntries(IMPORT_FIELDS);

// ---------- Stats periods ----------
// Ranges of local dates, both ends included. A week runs Monday to Sunday.
export const PERIOD_PRESETS = [['week', 'This week'], ['month', 'This month'], ['custom', 'Custom']];

export function presetRange(preset, now = new Date()) {
  const y = now.getFullYear();
  const m = now.getMonth();
  if (preset === 'month') {
    return { from: localDateISO(new Date(y, m, 1)), to: localDateISO(new Date(y, m + 1, 0)) };
  }
  const sinceMonday = (now.getDay() + 6) % 7;
  const monday = new Date(y, m, now.getDate() - sinceMonday);
  const sunday = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 6);
  return { from: localDateISO(monday), to: localDateISO(sunday) };
}

// A period as the PeriodPicker holds it: { preset, from, to }.
export function initialPeriod(preset = 'week') {
  return { preset, ...presetRange(preset) };
}

// "2026-11-02" -> "2 Nov" (short label under a chart).
export function formatDayShort(value) {
  const [y, m, d] = value.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}
