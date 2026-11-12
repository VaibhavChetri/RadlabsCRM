// Login.jsx
// ---------
// The login screen. Collects email + password, calls POST /auth/login,
// saves the returned token in localStorage, then sends the user to the
// dashboard.

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';

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
      // Save the token so api.js attaches it to future requests.
      localStorage.setItem('token', res.data.access_token);
      navigate('/dashboard');  // go to the leads dashboard
    } catch (err) {
      // 401 = wrong email/password; anything else = server/network problem.
      if (err.response && err.response.status === 401) {
        setError('Incorrect email or password.');
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
        <h1>Leads Login</h1>
        <p className="subtitle">Sign in to view your leads</p>

        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
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

        <p className="hint">Test account: test@client.com / test123</p>
      </form>
    </div>
  );
}
