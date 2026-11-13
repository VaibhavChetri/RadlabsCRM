// Button.jsx
// ----------
// One button for the whole CRM, modelled on the coss.com Button (21st.dev):
// one base style, a few variants, three sizes, a loading spinner, a clear
// focus ring. Plain CSS (index.css, "Buttons"), no Tailwind.
//
// Variants, by what the button does:
//   primary              the main action of a screen or form (Save, Add, Import)
//   call                 +1 Call: green, so it is found at a glance
//   outline              secondary actions (Export, Undo, Previous / Next)
//   ghost                quiet actions inside tables and bars (Reset password)
//   danger               a destructive action that is confirmed first (bulk Delete)
//   danger-outline       a destructive action next to normal ones (Delete lead)
//   danger-ghost         a quiet destructive action in a table (Deactivate)
//   link                 looks like a link (Clear filters, Open the existing lead)
// Sizes (coss.com desktop scale): sm 28px (tables, bars), md 32px, lg 38px (Login,
// the lead page +1 Call). Touch screens get a few px more (index.css).
// collapse: below 1100px only the icon shows (needs a `title`, used as the tooltip
// and the accessible name). For crowded table rows.
//
//   <Button variant="call" size="sm" icon="phone" loading={busy}>+1 Call</Button>
// A <Link> styled as a button: className={buttonClass({ variant: 'outline' })}.

import Icon from './Icon';
import { buttonClass } from './buttonClass';

export default function Button({
  variant, size, block, className, icon, iconAfter, loading = false, collapse = false,
  disabled, type = 'button', children, ...props
}) {
  return (
    <button
      type={type}
      className={buttonClass({
        variant, size, block, className: [className, collapse && 'btn-collapse'].filter(Boolean).join(' '),
      })}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <span className="btn-spinner" aria-hidden="true" /> : icon && <Icon name={icon} />}
      {collapse ? <span className="btn-label">{children}</span> : children}
      {iconAfter && !loading && <Icon name={iconAfter} />}
    </button>
  );
}
