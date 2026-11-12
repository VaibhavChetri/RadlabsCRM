// api.js
// ------
// One axios instance for the whole app.
// - Base URL comes from VITE_API_BASE_URL (frontend/.env), so hosting later
//   needs no code change.
// - Adds the saved login token to every request.
// - On 401 (token missing, expired, or user deactivated) it logs out.

import axios from 'axios';

export const TOKEN_KEY = 'token';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const isLogin = err.config?.url?.includes('/auth/login');
    if (err.response?.status === 401 && !isLogin) {
      localStorage.removeItem(TOKEN_KEY);
      window.location.assign('/login');
    }
    return Promise.reject(err);
  },
);

export default api;
