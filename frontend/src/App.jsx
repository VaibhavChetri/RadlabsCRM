// App.jsx
// -------
// Routes:
//   /login         public login screen
//   /              Home: "My call list today"
//   /leads         all leads + "Add lead" form
//   /leads/:uuid   one lead: every field, status, calls, notes
//   /import        import leads from an .xlsx / .csv file, plus import history
//   /stats         Team stats: one row per person for a chosen period

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { TOKEN_KEY } from './api';
import Layout from './components/Layout';
import Home from './pages/Home';
import Login from './pages/Login';
import Leads from './pages/Leads';
import LeadDetail from './pages/LeadDetail';
import Import from './pages/Import';
import TeamStats from './pages/TeamStats';

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
          <Route path="/" element={<Home />} />
          <Route path="/leads" element={<Leads />} />
          <Route path="/leads/:uuid" element={<LeadDetail />} />
          <Route path="/import" element={<Import />} />
          <Route path="/stats" element={<TeamStats />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
