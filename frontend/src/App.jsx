// App.jsx
// -------
// Sets up the 2 routes the app needs and protects the dashboard.
//   /login      -> the login screen (public)
//   /dashboard  -> the leads dashboard (only if logged in)
//   /           -> bounce to the right place depending on login state

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';

// A small wrapper: if there's no token, kick the user to /login.
function ProtectedRoute({ children }) {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        {/* Anything else -> send to dashboard (which itself guards for login). */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
