// Layout.jsx
// ----------
// App bar for every logged-in screen: brand, main links (segmented, with icons),
// who is logged in (initials, name, role), log out.
// The links are buttons, not <a> tags, so the browser shows no URL preview on hover.
// A white pill slides to the current page; each page fades in.
// The Team (admin) link shows only for admins.
// Loads the current user from GET /auth/me and passes it to pages via
// the router outlet context.

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import api, { TOKEN_KEY } from '../api';
import Button from './Button';
import Icon from './Icon';

// Main links. Team is for admins only.
const NAV = [
  { to: '/', label: 'My calls', icon: 'phone' },
  { to: '/leads', label: 'All leads', icon: 'list' },
  { to: '/import', label: 'Import', icon: 'upload' },
  { to: '/stats', label: 'Team stats', icon: 'barChart' },
  { to: '/team', label: 'Team', icon: 'users', adminOnly: true },
];

// "/" only on the home page; the others also for their sub-pages (e.g. /leads/<uuid>).
const isCurrent = (to, path) => (to === '/' ? path === '/' : path === to || path.startsWith(`${to}/`));

export default function Layout() {
  const [me, setMe] = useState(null);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const navRef = useRef(null);
  const [pill, setPill] = useState(null); // { left, width } of the current link
  const items = NAV.filter((item) => !item.adminOnly || me?.role === 'admin');

  // Move the white pill under the current link (and after resizes / the Team link appearing).
  const placePill = useCallback(() => {
    const current = navRef.current?.querySelector('[aria-current="page"]');
    setPill(current ? { left: current.offsetLeft, width: current.offsetWidth } : null);
  }, []);
  useLayoutEffect(placePill, [placePill, pathname, me]);
  useEffect(() => {
    window.addEventListener('resize', placePill);
    return () => window.removeEventListener('resize', placePill);
  }, [placePill]);

  useEffect(() => {
    // A 401 here is handled by the api interceptor (it logs out).
    api.get('/auth/me').then((res) => setMe(res.data)).catch(() => {});
  }, []);

  const handleLogout = () => {
    localStorage.removeItem(TOKEN_KEY);
    navigate('/login', { replace: true });
  };

  const initials = (me?.name || '')
    .split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');

  return (
    <>
      <header className="appbar">
        <div className="appbar-inner">
          <button type="button" className="brand" aria-label="Radlabs CRM, home" onClick={() => navigate('/')}>
            <img className="brand-mark" src="/logo.png" alt="" width="24" height="30" />
            <span className="brand-name">Radlabs <span>CRM</span></span>
          </button>
          <nav className="nav" aria-label="Main" ref={navRef}>
            {pill && (
              <span className="nav-pill" aria-hidden="true"
                style={{ width: pill.width, transform: `translateX(${pill.left}px)` }} />
            )}
            {items.map((item) => {
              const current = isCurrent(item.to, pathname);
              return (
                <button key={item.to} type="button" aria-current={current ? 'page' : undefined}
                  onClick={() => navigate(item.to)}>
                  <Icon name={item.icon} />{item.label}
                </button>
              );
            })}
          </nav>
          <div className="appbar-user">
            {me && (
              <div className="me" title={`${me.name} (${me.role === 'admin' ? 'Admin' : 'Member'})`}>
                <span className="avatar" aria-hidden="true">{initials}</span>
                <span className="me-text">
                  <span className="me-name">{me.name}</span>
                  <span className="me-role">{me.role === 'admin' ? 'Admin' : 'Member'}</span>
                </span>
              </div>
            )}
            <Button variant="ghost" size="sm" icon="logOut" collapse title="Log out" onClick={handleLogout}>
              Log out
            </Button>
          </div>
        </div>
      </header>
      <main className="page">
        <div key={pathname} className="page-in">
          <Outlet context={{ me }} />
        </div>
      </main>
    </>
  );
}
