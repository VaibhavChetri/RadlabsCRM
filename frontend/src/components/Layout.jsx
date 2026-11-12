// Layout.jsx
// ----------
// Top bar for every logged-in screen: app name, nav, who is logged in, log out.
// Loads the current user from GET /auth/me and passes it to pages via
// the router outlet context.

import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import api, { TOKEN_KEY } from '../api';

export default function Layout() {
  const [me, setMe] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    // A 401 here is handled by the api interceptor (it logs out).
    api.get('/auth/me').then((res) => setMe(res.data)).catch(() => {});
  }, []);

  const handleLogout = () => {
    localStorage.removeItem(TOKEN_KEY);
    navigate('/login', { replace: true });
  };

  return (
    <div className="page">
      <header className="topbar">
        <div className="topbar-left">
          <span className="brand">Radlabs CRM</span>
          <nav className="nav">
            <NavLink to="/leads">All leads</NavLink>
          </nav>
        </div>
        <div className="topbar-right">
          {me && <span className="me">{me.name}</span>}
          <button className="secondary" onClick={handleLogout}>Log out</button>
        </div>
      </header>
      <Outlet context={{ me }} />
    </div>
  );
}
