# Plan: Radlabs CRM — Phase 1

> Source PRD: [docs/prd-phase1-radlabs-crm.md](../docs/prd-phase1-radlabs-crm.md) (12 Nov 2026). Story numbers below refer to that PRD.

Approach: tracer bullets. Phase 1 is a thin path through every layer (DB → API → UI → tests). Every later phase adds one complete feature on top that can be demoed.

## Architectural decisions

Durable decisions that apply across all phases:

- **Stack**: FastAPI + SQLAlchemy · MySQL 9.7 (`mysql@9.7`, database `leadsdb`) · React + Vite + React Router · CSS-only charts (no chart library).
- **Config**: all settings from environment variables: database URL, JWT secret, allowed frontend origin, frontend API base URL. SMTP variables kept but unused until Phase 2.
- **Auth**: JWT bearer token. The token holds the user's public uuid and role. Roles: `admin`, `member`. Everyone sees all leads; only admin routes check the role. Inactive users cannot log in, and their tokens are rejected.
- **IDs**: every table has an internal integer id. Users and leads also have a public uuid. URLs and API responses use uuids only.
- **Time**: stored in UTC, shown in browser local time. "Today" and date ranges use the user's local date (sent by the client as dates).
- **Schema**:
  - `users` (uuid, name, email unique, password_hash, role, is_active, created_at)
  - `statuses` (name, sort_order, is_exit), seeded: New, Attempted, Connected, Interested, Meeting booked, Proposal sent, Won, Lost, Not interested, Do not call (last 4 = exit)
  - `leads` (uuid; first_name, last_name, job_title, email, phone, phone_2, linkedin_url, company, website, industry, company_size, city, country; source; priority hot|warm|cold; status_id; owner_id nullable; call_attempts, last_called_at, next_follow_up; created_by, created_at, updated_at)
  - `lead_notes` (lead_id, user_id, body, created_at): the Notes thread, never edited
  - `calls` (lead_id, user_id, called_at)
  - `status_changes` (lead_id, from_status_id nullable, to_status_id, user_id, changed_at)
  - `import_presets` (name unique, mapping JSON, is_builtin)
  - `imports` (user_id, file_name, source, added, updated, skipped, created_at)
- **Source list** (fixed in code): Apollo, LinkedIn, Referral, Event, Cold list, Other.
- **Routes**:
  - `POST /auth/login`, `GET /auth/me`
  - `GET/POST /users`, `PATCH /users/{uuid}`, `POST /users/{uuid}/reset-password` (admin)
  - `GET /statuses`, `GET /owners` (active users for Owner dropdowns; any logged-in user)
  - `GET/POST /leads`, `GET/PATCH/DELETE /leads/{uuid}`, `POST /leads/{uuid}/call`, `GET/POST /leads/{uuid}/notes`, `POST /leads/bulk`, `GET /leads/today`, `GET /leads/export`
  - `POST /imports/preview`, `POST /imports`, `GET /imports`, `GET/POST /imports/presets`
  - `GET /stats/summary?scope=me|team&from&to`, `GET /stats/team?from&to`
- **Frontend routes**: `/login`, `/` (Home), `/leads`, `/leads/:uuid`, `/import`, `/stats`, `/team`.
- **Write rule**: every change to a lead goes through the Lead service, so call rows and status history are always written, including for bulk actions.
- **Testing**: pytest against a separate test MySQL database created fresh for each test run. No database mocks. Tests check behaviour from outside (inputs → outputs, HTTP → response and DB state).

---

## Phase 1: Tracer bullet — new CRM skeleton

**User stories**: 1, 2, 3, 11, 31, 50, 62, 67, 85, 86, 87, 88, 89

### What to build

Swap the client-inbox foundation for the CRM foundation and prove one full path works. A one-time script exports the old leads and client list to an Excel backup. A migration drops the old tables, creates the new schema, seeds the 10 statuses, and creates the admin user `Radlabs@leads.com` (role admin, same password as now). Login works against `users`; `/auth/me` returns the user. A logged-in user can add a lead with a simple form (name, company, email, phone) and see it in a basic list with an "Added to CRM" column (and "Added by"). The public website-form endpoint and the new-lead email alert are removed. The pytest setup with a throwaway test database is in place, with first API tests.

### Acceptance criteria

- [x] Excel backup of the 13 old leads and the old client list exists before any table is dropped.
- [x] Fresh database has the new tables, 10 statuses in order, and exactly one user (admin).
- [x] `Radlabs@leads.com` / `Radlabs123` logs in; a wrong password shows a clear error; logout works.
- [x] Adding a lead via the form shows it in the list with status New, "Added to CRM" date, and the creator's name.
- [x] A new lead writes a first `status_changes` row (none → New).
- [x] No route accepts leads without a login; the old submit route is gone.
- [x] `pytest` runs green: login ok, login wrong, unauthenticated request rejected, create lead, list leads.

---

## Phase 2: Lead detail — fields, status, calls, notes

**User stories**: 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 52, 53, 54

### What to build

A full lead page. Every field is shown and editable. Phone shows tap-to-call and a WhatsApp link; LinkedIn and website open in a new tab. Status dropdown with the 10 stages; Priority (Hot/Warm/Cold); Owner dropdown (active users plus "Unassigned"). A call block with "+1 Call" (adds to attempts, sets Last called, writes a `calls` row), the attempts count, Last called, and a Next follow-up date picker. A Notes thread: write a note, save it, and it is kept with the author's name and the time. The write box sits on top; the thread is below it, newest first. Notes cannot be edited or deleted; they go only with the lead, so a new owner gets the full story. (Changed on 12 Nov 2026 from the planned single Notes box + Stamp button.) "Do not call" is clearly marked. Delete asks for confirmation. All writes go through the Lead service, which records status history and signs each note.

### Acceptance criteria

- [x] Editing any field saves and is shown after reload; `updated_at` changes.
- [x] Status change writes a `status_changes` row with from, to, user and time.
- [x] "+1 Call" adds 1 to attempts, sets Last called, and writes one `calls` row.
- [x] The follow-up date saves and clears.
- [x] Saving a note adds it to the thread with author and time; every user sees the whole thread, newest first, below the write box.
- [x] Do-not-call leads show a clear warning badge.
- [x] `migrate_phase2.py` moves any old Notes box text into the thread and drops the old columns.
- [x] Delete needs a confirmation and removes the lead with its calls, history and notes.
- [x] Lead service tests: +1 call, status history, add note (author, time, empty refused).

---

## Phase 3: Home — "My call list today"

**User stories**: 55, 56, 57, 58, 59, 60, 61

### What to build

The home screen after login. For the logged-in user: overdue follow-ups (red), then today's follow-ups, then their New leads sorted Hot → Warm → Cold. Leads in exit statuses never appear. Each row has +1 Call and a status dropdown inline, and a click opens the lead. Served by `GET /leads/today`. Leave a space at the top for the analytics strip (Phase 6).

### Acceptance criteria

- [x] Only the user's own leads appear; exit-status leads are excluded.
- [x] Order: overdue → due today → New leads by priority.
- [x] Overdue rows are red.
- [x] Inline +1 Call and status change work, and the list refreshes.
- [x] API test with seeded leads checks the sections and their order.

---

## Phase 4: All leads — table, bulk actions, export

**User stories**: 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72

### What to build

The full leads table. Search across name, company, email and phone. Filters: status, owner (including Unassigned), source, priority, date-added range. Sort by date added, last called, next follow-up, priority, company. Pages with a total count. Checkbox selection with bulk Set status / Set owner / Set priority / Delete (confirm). Bulk actions go through the Lead service per lead, so history is written. "Export to Excel" downloads the current filtered list with all fields, including Added to CRM, status, owner and notes. Filters are kept in the URL, so a view can be shared or reloaded.

### Acceptance criteria

- [x] Search and every filter narrow the results correctly; they can be combined.
- [x] Sorting and paging work with thousands of seeded leads, without noticeable delay.
- [x] Bulk status change writes one history row per lead.
- [x] Bulk delete needs a confirmation.
- [x] Export gives a valid .xlsx matching the current filter.
- [x] API tests: filters, sort, paging, bulk update, export.

---

## Phase 5: Import — upload, map, dedupe, assign, report

**User stories**: 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 32, 33

### What to build

The Lead matcher and the Import engine, end to end. The matcher normalises email (lowercase), phone (digits, last 10) and LinkedIn URL (lowercase, no trailing slash or query), and matches in that order. On a match it fills empty fields only; status, owner, notes, call fields and priority are never changed. The manual "Add lead" form uses the matcher too: a duplicate returns 409, and the UI offers to open the existing lead.

Import wizard: upload .xlsx/.csv (max 5 MB / 5,000 rows) → pick Source, Preset and "Assign to" (a user / split evenly across active users / unassigned) → column mapping, auto-suggested from headers, with a built-in Apollo preset; each column can be changed or skipped → preview of the first 5 mapped rows → import. Rows with no email, phone or LinkedIn are skipped; duplicates inside the file are merged. The whole import runs in one transaction. A report shows added / updated / skipped with reasons, and can be downloaded as .xlsx. The mapping can be saved as a named preset. An import history list shows who, when, file, source and counts.

### Acceptance criteria

- [ ] An Apollo CSV export maps with no manual change via the built-in preset.
- [ ] Re-uploading the same file adds 0 leads and changes no status, owner, notes or call fields.
- [ ] A file with a new phone for an existing lead fills that phone only if it was empty.
- [ ] Rows with no contact info are skipped with the reason "no contact info".
- [ ] "Split evenly" spreads leads round-robin across active users.
- [ ] A bad row that causes a DB error rolls back the whole import.
- [ ] Wrong file type or too-large file is refused with a clear message.
- [ ] A manual add of an existing email returns 409 and the UI links to the existing lead.
- [ ] Import engine + matcher tests with sample Apollo, messy Excel and CSV files cover all of the above.

---

## Phase 6: Analytics — strip and Team stats

**User stories**: 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84

### What to build

The Stats engine plus two views. Analytics strip on the Home screen: toggles Me / Team and This week / This month / Custom dates. Cards: Total leads, Added, Calls, Follow-ups due, Meetings booked, Won, Conversion % (Won ÷ added in range). Visual CSS charts: pipeline funnel across all 10 stages, calls per day, leads added per day, leads by source. Days with no data show as zero. "Meetings booked" and "Won" count status changes inside the range. Team stats page: one row per person (including deactivated users who have activity in the range) with calls, leads by current status, meetings booked and won for the chosen period.

### Acceptance criteria

- [ ] Toggles change every number and chart together.
- [ ] Numbers match a hand-counted seeded dataset for week, month and a custom range.
- [ ] Moving a lead out of "Won" later does not remove it from "Won" for the past range.
- [ ] Charts have no missing days.
- [ ] Team stats includes deactivated users with activity in the range.
- [ ] Stats engine tests with seeded users, leads, calls and status changes over several weeks.

---

## Phase 7: Team admin

**User stories**: 4, 5, 6, 7, 8, 9, 10, 12

### What to build

A Team page for the admin only: list users; add a user (name, email, temporary password, role); deactivate or reactivate; reset a password. Members do not see the page, and the API refuses them. Deactivated users cannot log in, and their existing tokens stop working. Their leads stay; the page offers "Reassign all their leads to…" (through the Lead service, so history is written). Owner dropdowns show only active users.

### Acceptance criteria

- [ ] Admin can add a user who can then log in and see all leads.
- [ ] A member gets 403 on every `/users` route, and the Team link is hidden for them.
- [ ] A deactivated user is refused at login, and their old token gets 401.
- [ ] Reassign moves all their leads and keeps their past stats.
- [ ] Password reset works; the old password stops working.
- [ ] API tests for permissions, deactivation and reset.
