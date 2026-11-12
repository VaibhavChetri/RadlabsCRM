// App.jsx
// -------
// Routes:
//   /login   public login screen
//   /leads         all leads + "Add lead" form
//   /leads/:uuid   one lead: every field, status, calls, notes
//   /        Home (call list arrives in Phase 3; for now it opens /leads)

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { TOKEN_KEY } from './api';
import Layout from './components/Layout';
import Login from './pages/Login';
import Leads from './pages/Leads';
import LeadDetail from './pages/LeadDetail';

function ProtectedRoute({ children }) {
  return localStorage.getItem(TOKEN_KEY) ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<Navigate to="/leads" replace />} />
          <Route path="/leads" element={<Leads />} />
          <Route path="/leads/:uuid" element={<LeadDetail />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
