// buttonClass.js
// --------------
// The class list for a .btn (see Button.jsx for the variants and sizes).
// Use it to style something that is not a <button> as one, e.g. a router <Link>.

export function buttonClass({ variant = 'primary', size = 'md', block = false, className = '' } = {}) {
  return ['btn', `btn-${variant}`, size !== 'md' && `btn-${size}`, block && 'btn-block', className]
    .filter(Boolean).join(' ');
}
