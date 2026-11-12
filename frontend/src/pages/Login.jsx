// Login.jsx
// ---------
// Login screen. POST /auth/login, save the token, go to Home.

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { TOKEN_KEY } from '../api';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();        // stop the browser reloading the page
    setError('');
    setLoading(true);
    try {
      const res = await api.post('/auth/login', { email, password });
      localStorage.setItem(TOKEN_KEY, res.data.access_token);
      navigate('/', { replace: true });
    } catch (err) {
      // 401 = wrong email/password; anything else = server/network problem.
      if (err.response && err.response.status === 401) {
        setError('Incorrect email or password. Try again, or ask the admin to reset it.');
      } else {
        setError('Could not reach the server. Is the backend running?');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="centered-page">
      <form className="card" onSubmit={handleLogin}>
        <h1>Radlabs CRM</h1>
        <p className="subtitle">Sign in with your team account</p>

        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@radlabs.tech"
            required
          />
        </label>

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
          />
        </label>

        {error && <div className="error">{error}</div>}

        <button type="submit" disabled={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
