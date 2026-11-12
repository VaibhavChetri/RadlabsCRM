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
