// Team.jsx
// --------
// Team admin (route /team). Admin only: the nav link is hidden for members,
// and the API answers 403 to them anyway.
//   - list everyone (active first), with the leads they own now
//   - add a person: name, email, temporary password, role
//   - change role, deactivate / reactivate
//   - reset a password (the old one stops working)
//   - "Reassign all their leads to…" another active person, or Unassigned
// A deactivated person cannot log in and their open session stops working.
// Their leads stay, and their past stats stay on the Team stats page.
// Data: GET/POST /users, PATCH /users/:uuid, POST /users/:uuid/reset-password,
//       POST /users/:uuid/reassign-leads

import { useCallback, useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import api from '../api';
import Button from '../components/Button';
import { errorMessage, formatDate, localDateISO } from '../format';

const EMPTY_USER = { name: '', email: '', password: '', role: 'member' };
const UNASSIGNED = '';

export default function Team() {
  const { me } = useOutletContext();
  const [users, setUsers] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [panel, setPanel] = useState(null); // { uuid, kind: 'reset' | 'reassign' }

  const load = useCallback(() => {
    return api.get('/users')
      .then((res) => { setUsers(res.data); setError(''); })
      .catch((err) => setError(errorMessage(err, 'Could not load the team.')));
  }, []);

  useEffect(() => {
    if (me?.role === 'admin') load();
  }, [me, load]);

  if (!me) return <p className="hint">Loading…</p>;
  if (me.role !== 'admin') {
    return <div className="error">Only the admin can manage the team.</div>;
  }

  const done = (message) => {
    setNotice(message);
    setPanel(null);
    return load();
  };

  const run = async (action, fallback) => {
    setError('');
    setNotice('');
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err, fallback));
    }
  };

  const changeRole = (user, role) => run(async () => {
    await api.patch(`/users/${user.uuid}`, { role });
    await done(`${user.name} is now ${role === 'admin' ? 'an admin' : 'a member'}.`);
  }, 'Could not change the role.');

  const toggleActive = (user) => {
    if (user.is_active) {
      const leadsLine = user.leads
        ? ` Their ${user.leads} lead(s) stay with them until you reassign them.`
        : '';
      if (!window.confirm(`Deactivate ${user.name}? They will not be able to log in.${leadsLine}`)) {
        return;
      }
    }
    run(async () => {
      await api.patch(`/users/${user.uuid}`, { is_active: !user.is_active });
      await done(`${user.name} is ${user.is_active ? 'deactivated' : 'active again'}.`);
    }, 'Could not change the account.');
  };

  const togglePanel = (uuid, kind) => {
    setPanel(panel?.uuid === uuid && panel.kind === kind ? null : { uuid, kind });
  };

  const activeUsers = (users || []).filter((u) => u.is_active);

  return (
    <>
      <div className="lead-head">
        <div>
          <h1>Team</h1>
          <p className="subtitle">Add people, switch off old accounts, reset passwords.</p>
        </div>
      </div>

      <AddUserForm onAdded={(user) => run(() => done(`${user.name} can now log in.`))} />

      {error && <div className="error">{error}</div>}
      {notice && <div className="notice">{notice}</div>}
      {!users && !error && <p className="hint">Loading the team…</p>}

      {users && (
        <div className="card">
          <div className="table-wrap">
            <table className="team-admin-table stack-table">
              <thead>
                <tr>
                  <th>Person</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th className="num">Leads owned</th>
                  <th>Added</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => {
                  const isMe = user.uuid === me.uuid;
                  const open = panel?.uuid === user.uuid ? panel.kind : null;
                  return (
                    <UserRows
                      key={user.uuid}
                      user={user}
                      isMe={isMe}
                      open={open}
                      targets={activeUsers.filter((u) => u.uuid !== user.uuid)}
                      onRole={(role) => changeRole(user, role)}
                      onToggleActive={() => toggleActive(user)}
                      onPanel={(kind) => togglePanel(user.uuid, kind)}
                      onReset={(password) => run(async () => {
                        await api.post(`/users/${user.uuid}/reset-password`, { password });
                        await done(`Password reset for ${user.name}. Their old password no longer works.`);
                      }, 'Could not reset the password.')}
                      onReassign={(toUuid, toName) => run(async () => {
                        const res = await api.post(`/users/${user.uuid}/reassign-leads`,
                          { to_uuid: toUuid || null });
                        await done(`${res.data.count} lead(s) moved from ${user.name} to ${toName}.`);
                      }, 'Could not reassign the leads.')}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

function UserRows({ user, isMe, open, targets, onRole, onToggleActive, onPanel, onReset, onReassign }) {
  return (
    <>
      <tr className={user.is_active ? undefined : 'row-inactive'}>
        <td className="cell-title">
          {user.name}
          {isMe && <span className="badge small-badge">You</span>}
          {!user.is_active && <span className="badge small-badge">Deactivated</span>}
        </td>
        <td data-label="Email">{user.email}</td>
        <td data-label="Role">
          <select
            className="compact"
            value={user.role}
            disabled={isMe}
            title={isMe ? 'You cannot change your own role' : undefined}
            onChange={(e) => onRole(e.target.value)}
          >
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select>
        </td>
        <td data-label="Leads owned" className="num">{user.leads}</td>
        <td data-label="Added">{formatDate(localDateISO(new Date(user.created_at)))}</td>
        <td data-label="Actions" className="cell-wide">
          <div className="row-actions">
            <Button variant="ghost" size="sm" icon="key" collapse title="Reset password"
              aria-expanded={open === 'reset'}
              onClick={() => onPanel('reset')}>
              Reset password
            </Button>
            {user.leads > 0 && (
              <Button variant="ghost" size="sm" icon="swap" collapse title="Reassign leads"
                aria-expanded={open === 'reassign'}
                onClick={() => onPanel('reassign')}>
                Reassign leads
              </Button>
            )}
            {!isMe && (
              <Button variant={user.is_active ? 'danger-ghost' : 'ghost'} size="sm"
                icon={user.is_active ? 'userX' : 'userCheck'} collapse
                title={user.is_active ? 'Deactivate' : 'Reactivate'} onClick={onToggleActive}>
                {user.is_active ? 'Deactivate' : 'Reactivate'}
              </Button>
            )}
          </div>
        </td>
      </tr>
      {open === 'reset' && (
        <tr className="panel-row">
          <td colSpan={6}><ResetPasswordForm name={user.name} onSubmit={onReset} /></td>
        </tr>
      )}
      {open === 'reassign' && (
        <tr className="panel-row">
          <td colSpan={6}>
            <ReassignForm user={user} targets={targets} onSubmit={onReassign} />
          </td>
        </tr>
      )}
    </>
  );
}

function AddUserForm({ onAdded }) {
  const [form, setForm] = useState(EMPTY_USER);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const res = await api.post('/users', form);
      setForm(EMPTY_USER);
      onAdded(res.data);
    } catch (err) {
      setError(errorMessage(err, 'Could not add the person. Please try again.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="card add-lead" onSubmit={handleSubmit}>
      <h2>Add a team member</h2>
      <div className="form-grid">
        <label>
          Name
          <input value={form.name} onChange={update('name')} required />
        </label>
        <label>
          Email
          <input type="email" value={form.email} onChange={update('email')} required />
        </label>
        <label>
          Temporary password
          <input
            value={form.password}
            onChange={update('password')}
            minLength={8}
            required
            autoComplete="new-password"
            placeholder="At least 8 characters"
          />
        </label>
        <label>
          Role
          <select value={form.role} onChange={update('role')}>
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select>
        </label>
      </div>
      {error && <div className="error">{error}</div>}
      <Button type="submit" icon="userPlus" loading={saving}>
        {saving ? 'Adding…' : 'Add team member'}
      </Button>
    </form>
  );
}

function ResetPasswordForm({ name, onSubmit }) {
  const [password, setPassword] = useState('');
  return (
    <form
      className="panel-form"
      onSubmit={(e) => { e.preventDefault(); onSubmit(password); }}
    >
      <label>
        New password for {name}
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={8}
          required
          autoFocus
          autoComplete="new-password"
          placeholder="At least 8 characters"
        />
      </label>
      <Button type="submit" icon="key">Reset password</Button>
    </form>
  );
}

function ReassignForm({ user, targets, onSubmit }) {
  const [toUuid, setToUuid] = useState(targets[0]?.uuid ?? UNASSIGNED);
  const toName = targets.find((t) => t.uuid === toUuid)?.name ?? 'Unassigned';
  return (
    <form
      className="panel-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (window.confirm(`Move all ${user.leads} lead(s) from ${user.name} to ${toName}?`)) {
          onSubmit(toUuid, toName);
        }
      }}
    >
      <label>
        Reassign all {user.leads} lead(s) of {user.name} to
        <select value={toUuid} onChange={(e) => setToUuid(e.target.value)}>
          {targets.map((t) => <option key={t.uuid} value={t.uuid}>{t.name}</option>)}
          <option value={UNASSIGNED}>Unassigned</option>
        </select>
      </label>
      <Button type="submit" icon="swap">Reassign leads</Button>
    </form>
  );
}
