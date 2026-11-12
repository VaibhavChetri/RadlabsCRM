// api.js
// -------
// ONE axios instance the whole app uses to call the backend.
// An "interceptor" runs before every request and automatically attaches
// the saved login token, so we never have to remember to add it by hand.

import axios from 'axios';

const api = axios.create({
  // Where our FastAPI backend lives during local development.
  baseURL: 'http://127.0.0.1:8000',
});

// Before each request goes out: if we have a token saved, add the
// Authorization header. This is what makes protected endpoints work.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
