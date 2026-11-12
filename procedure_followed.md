# Procedure Followed — Lead Management System

> A plain-English running log of **every step** we take to build this system.
> Written so that *any* developer joining midway can read top-to-bottom and
> understand **what** was done, **how**, and **why**.
>
> Build order (from the senior's prompt):
> 1. **Database design (MySQL)** ← we are here
> 2. FastAPI skeleton + login (JWT)
> 3. `POST /leads/submit` (test in Postman)
> 4. `GET /leads/` (only the logged-in client's leads)
> 5. `GET /leads/export` (Excel download)
> 6. `PATCH /leads/{id}/status`
> 7. React Login page
> 8. React Dashboard (leads table)
> 9. Email notification on new lead
> 10. Deploy (GCP)

---

## Step 1 — Database Design (MySQL)

### What we built
Two database tables that the whole system stands on:

| Table     | What it holds                          | Plain-English meaning                              |
|-----------|----------------------------------------|----------------------------------------------------|
| `clients` | The businesses who log into the dashboard | "Who is allowed to log in, and what's their password" |
| `leads`   | Every contact-form submission          | "The actual enquiries, each one tied to one client"   |

### The "one client can never see another client's leads" rule
Every lead has a `client_id` column. It is a **foreign key** pointing at
`clients.id`. This is the backbone of the whole product:
- A lead **must** belong to a real client (MySQL refuses a lead with a
  client_id that doesn't exist).
- When a client logs in, we will only ever fetch leads `WHERE client_id =`
  *their own id* (taken from their login token, never from the request).

### Files created in this step
| File                              | Purpose                                                        |
|-----------------------------------|---------------------------------------------------------------|
| `database/schema.sql`             | Creates the `leadsdb` database + the `clients` and `leads` tables. |
| `database/create_test_client.py`  | Inserts one test login account (password stored **hashed**).  |

### Small, deliberate improvements over the bare spec
- **`utf8mb4`** on the database → supports every language + emojis in messages.
- **Indexes** on `leads.client_id` and `leads.status` → the dashboard filters
  by these on every request, so we make those lookups fast from day one.
- **Test client created via a Python script, not raw SQL** → because the
  password has to be a bcrypt *hash*, which you cannot type by hand. This is
  why the test client is inserted in Step 2 (after the hashing library is
  installed), not with raw SQL here.

### Notification email
The senior's prompt says "store the client's notification email in the
`clients` table." The `clients.email` column already serves this purpose — it
is both the **login id** and the **address new-lead emails go to**. No extra
column needed.

### How to run / verify this step
```bash
# 1. Create the database + tables:
mysql -u root -p < database/schema.sql

# 2. Verify (inside the mysql prompt):
mysql -u root -p
   USE leadsdb;
   SHOW TABLES;        -- expect: clients, leads
   DESCRIBE clients;
   DESCRIBE leads;
```
The test client row itself is inserted in **Step 2** with
`python database/create_test_client.py` (it needs the libraries we install then).

### Environment notes (so the next dev can reproduce)
- **MySQL 9.6** installed via Homebrew, running as a background service
  (`brew services start mysql`). Start/stop with `brew services start|stop mysql`.
- Root user has **no password** locally (Homebrew default). That's fine for
  local dev; on GCP Cloud SQL we'll set a real password.
- ⚠️ Use the Homebrew client `/opt/homebrew/opt/mysql/bin/mysql`, not the older
  Anaconda 5.7 `mysql` that sits earlier on the PATH (version mismatch).

### Status of Step 1
- [x] `schema.sql` written (database + both tables)
- [x] `create_test_client.py` written (runs in Step 2)
- [x] MySQL 9.6 installed & running (Homebrew)
- [x] Schema run against the live server — `clients` + `leads` tables verified
- [x] Test client inserted in Step 2 (`test@client.com` / `test123`)

---

## Step 2 — FastAPI Skeleton + Login (JWT)

### What we built
The backend application itself, and a working **login** so a client can get
a token to prove who they are.

### The backend folder, file by file
| File | Plain-English job |
|------|-------------------|
| `backend/main.py` | The app's front door. Turns on CORS (so React can call it) and plugs in all the routes. This is what the server runs. |
| `backend/database.py` | The one place that knows how to connect to MySQL. Hands each request a short-lived DB session. |
| `backend/models.py` | Python mirrors of the `clients` and `leads` tables. |
| `backend/schemas.py` | The "shapes" of data going in/out (e.g. login needs email+password). Makes sure we never send a password back out. |
| `backend/auth.py` | Security core: hash/verify passwords (bcrypt) + create/read JWT login tokens. |
| `backend/routes/auth.py` | `POST /auth/login` — checks password, returns a token. |
| `backend/routes/clients.py` | `POST /clients/create` — make a new client (password hashed). |
| `backend/routes/leads.py` | Empty shell for now; lead endpoints come in Steps 3–6. |
| `backend/requirements.txt` | The list of libraries the project needs. |
| `backend/.env` | Secrets (DB connection, JWT key). **Not committed to git.** |
| `backend/.gitignore` | Tells git to ignore `.env`, the venv, and caches. |

### How login works (the important security bit)
1. React sends `{ email, password }` to `POST /auth/login`.
2. We find the client by email and check the password against the stored
   **bcrypt hash** (we never store or compare plain text).
3. If correct, we return a **JWT token** that secretly carries the client's id.
4. On every protected request later, we read the client id **out of that token**
   — never from the request body. This is the rule that keeps clients' data separate.

### How we set it up
```bash
cd backend
python3 -m venv venv                       # isolated library folder
./venv/bin/pip install -r requirements.txt # install everything
# (then, from project root) inserted the test client:
backend/venv/bin/python database/create_test_client.py
```

### Gotcha we handled in advance
`passlib` crashes with newer `bcrypt` (>= 4.1). We **pinned `bcrypt==4.0.1`** in
requirements.txt so this never bites you.

### How to run the server yourself
```bash
cd backend
./venv/bin/uvicorn main:app --reload
# Open the interactive API docs at:  http://127.0.0.1:8000/docs
```

### Tests we ran (all passed ✅)
| Test | Result |
|------|--------|
| `GET /` health check | `{"status":"ok"}` |
| Login with correct password | returns a JWT `access_token` |
| Login with wrong password | `401 Incorrect email or password` |

### Status of Step 2
- [x] Backend folder + all skeleton files created
- [x] Virtual environment + libraries installed
- [x] `/auth/login` working with JWT (verified)
- [x] `/clients/create` built (ready to test in Postman, Step 3)
- [x] CORS enabled for the React app

---

## Step 3 — Public Lead Submission + Postman Testing

### What we built
`POST /leads/submit` — the **public** endpoint a client's website contact form
posts to. No login needed (a website form can't log in). The form includes a
`client_id` so we know whose lead it is.

Safety touch: before saving, we check the `client_id` belongs to a real client.
If not, we return a clean `404` instead of letting the database throw a 500.

### Files changed
| File | Change |
|------|--------|
| `backend/schemas.py` | Added `LeadSubmit` (client_id, name, email, phone, message). |
| `backend/routes/leads.py` | Added the `POST /leads/submit` endpoint. |
| `postman/Lead_Management.postman_collection.json` | A ready-to-import Postman collection with every request pre-filled. |

### Tests we ran (all passed ✅)
| Test | Result |
|------|--------|
| Submit valid lead (client_id=1) | `{"message":"Lead received","lead_id":1}` |
| Submit with client_id=999 (doesn't exist) | `404 No client found with id 999` |
| Check the row landed in MySQL | lead present with `status='new'` |

### Postman — what it is and how we used it
Postman is a tool to send test requests to your API by hand (instead of writing
code). We created a collection file so the requests are pre-built; you import it
and click **Send**. The Login request auto-saves the token into a `{{token}}`
variable for the protected requests we build next.

### Status of Step 3
- [x] `POST /leads/submit` built and verified
- [x] Postman collection created and importable
- [x] Junior dev ran it in Postman — got `201 Created`, lead saved (id 2)
- [x] Verified the full loop in MySQL (Postman → backend → database)

### Postman beginner notes (for the next dev)
- If imported collections don't show, toggle **"Local View"** (bottom-left)
  and clear the sidebar filter box.
- `201 Created` = success, a new record was made. `404` = not found.
- Set method (GET/POST), URL, then **Body → raw → JSON** for POST requests.

---

## Step 4 — Get My Leads (protected) + data-isolation proof

### What we built
`GET /leads/` — the **protected** endpoint the dashboard calls to show a
client their own leads. It requires a login token.

### The one rule that matters
The `client_id` is taken from the **JWT token** (via `get_current_client`),
NOT from the request. So a client physically cannot ask for someone else's
leads — the only id we trust is the one baked into their verified token.

### Files changed
| File | Change |
|------|--------|
| `backend/schemas.py` | Added `LeadOut` (the shape of a lead sent back). |
| `backend/routes/leads.py` | Added `GET /leads/` (protected, filters by token's client_id). |
| `postman/...collection.json` | Added request "4. Get my leads" with Bearer auth. |

### Proof we ran (the important test) ✅
| Who | `GET /leads/` returned |
|-----|------------------------|
| Client 1 (test@client.com) | only their 2 leads |
| Client 2 (acme@example.com) | only their 1 lead |
| No token | `401 Unauthorized` |

### How a protected request works in Postman
Unlike the public endpoints, this one needs the **Authorization** tab set to
**Bearer Token** with value `{{token}}`. The Login request auto-saves the token
into `{{token}}`, so: run Login first, then this works.

### Status of Step 4
- [x] `GET /leads/` built (protected, token-filtered)
- [x] Data isolation proven across two clients
- [x] 401 returned when no token is sent
- [x] Junior dev ran it in Postman

---

## Step 5 — Export Leads to Excel (protected)

### What we built
`GET /leads/export` — builds an `.xlsx` Excel file of the logged-in client's
leads (using the `openpyxl` library) and sends it as a file download.

### How it works in plain terms
1. Fetch this client's leads (same token-based security as Step 4).
2. Create a spreadsheet in memory with columns:
   Name, Email, Phone, Message, Status, Submitted At.
3. Add one row per lead.
4. Send it back with a `Content-Disposition: attachment` header — that header
   is what makes the browser/Postman treat it as a *download* instead of text.

### Files changed
| File | Change |
|------|--------|
| `backend/routes/leads.py` | Added `GET /leads/export` (openpyxl + StreamingResponse). |
| `postman/...collection.json` | Added request "5. Export leads to Excel". |

### Tests we ran ✅
| Test | Result |
|------|--------|
| Download as Client 1 | real `.xlsx` file, 5KB |
| Correct headers | `attachment; filename=leads.xlsx` |
| Read the file back | header row + Client 1's 2 leads, correct |

### How to download it in Postman
A file download is special: click the **arrow next to the Send button** and
choose **"Send and Download"**, then save the file and open it in Excel.

### Status of Step 5
- [x] `GET /leads/export` built and verified (file opens, correct rows)
- [x] Junior dev downloads it in Postman + opens in Excel

### Postman beginner note (auth header gotcha)
For protected requests use **Authorization → Bearer Token**. If you paste a
token and get *"Invalid character in header content"*, you accidentally
included a trailing space/newline — remove it. Tokens expire after 60 min;
re-run Login to get a fresh one.

---

## Step 6 — Update Lead Status (protected)

### What we built
`PATCH /leads/{lead_id}/status` — moves a lead through `new → contacted → closed`.
(`PATCH` is the HTTP verb for "update part of an existing record".)

### Security + validation
- We find the lead by **both** its id AND the token's `client_id`, so a client
  can never edit another client's lead (they get a `404`).
- The status value is restricted by a `Literal` type — anything other than
  `new`/`contacted`/`closed` is auto-rejected with `422`.

### Files changed
| File | Change |
|------|--------|
| `backend/schemas.py` | Added `LeadStatusUpdate`. |
| `backend/routes/leads.py` | Added `PATCH /leads/{id}/status`. |
| `postman/...collection.json` | Added request "6. Update lead status". |

### Tests we ran ✅
| Test | Result |
|------|--------|
| Client 1 updates own lead | `contacted` ✅ |
| Client 1 edits Acme's lead | `404 Lead not found` ✅ |
| Invalid status "banana" | `422` rejected ✅ |
| DB check | only the intended lead changed ✅ |

### Backend is now feature-complete
All endpoints the senior listed for the backend are built & tested:
`/auth/login`, `/clients/create`, `/leads/submit`, `/leads/`, `/leads/export`,
`/leads/{id}/status`. Next up is the **React frontend** (Steps 7–8).

### Status of Step 6
- [x] `PATCH /leads/{id}/status` built and verified
- [x] Junior dev tries it in Postman (optional)

---

## Step 7 — React Login Page

### What we built
The frontend app (React + Vite) with a working **login screen**. A user enters
email + password, we call the backend, save the token, and send them to the
dashboard.

### How we set it up
```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install                       # base React libraries
npm install axios react-router-dom
npm run dev                        # starts the app at http://127.0.0.1:5173
```

### Files (under `frontend/src/`)
| File | Plain-English job |
|------|-------------------|
| `api.js` | One axios instance for all backend calls. Auto-attaches the saved token to every request. |
| `App.jsx` | The 2 routes (`/login`, `/dashboard`) and the guard that blocks the dashboard if you're not logged in. |
| `pages/Login.jsx` | The login form. Calls `POST /auth/login`, saves the token, redirects. |
| `pages/Dashboard.jsx` | Placeholder for now (proves login worked + logout). Real table comes in Step 8. |
| `index.css` | Simple, clean styling (plain CSS, no framework). |

### How login works front-to-back
1. You type email + password and submit.
2. `Login.jsx` calls `POST /auth/login` via `api.js`.
3. On success we save the token: `localStorage.setItem('token', ...)`.
4. We redirect to `/dashboard`. The `ProtectedRoute` sees a token and lets you in.
5. If you visit `/dashboard` with no token, you're bounced to `/login`.
6. Wrong password shows a friendly "Incorrect email or password" message.

### Verified ✅
- `npm run build` compiles with **no errors**.
- Dev server serves the app at `http://127.0.0.1:5173` (HTTP 200).
- Backend CORS already allows `localhost:5173`, so the browser can call the API.

### How to run BOTH servers (you need two terminals)
```bash
# Terminal 1 — backend
cd backend && ./venv/bin/uvicorn main:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

### Status of Step 7
- [x] React app scaffolded (Vite) + axios + react-router-dom
- [x] Login page, routing, protected route, api client built
- [x] Compiles cleanly; both servers running
- [x] Junior dev logs in via the browser

---

## Step 8 — React Dashboard (leads table)

### What we built
The real dashboard the client sees after login: a table of their leads with a
status dropdown on each row, an Export-to-Excel button, and a friendly empty
state.

### Files (under `frontend/src/`)
| File | Plain-English job |
|------|-------------------|
| `pages/Dashboard.jsx` | Fetches leads on load, shows the table, handles loading/empty/error, runs the Excel download. |
| `components/LeadsTable.jsx` | Draws the table rows (Name, Email, Phone, Message, Status, Submitted). |
| `components/StatusDropdown.jsx` | The per-row dropdown; calls `PATCH /leads/{id}/status` on change. |

### Nice touches we added
- **Loading state** while leads are fetched.
- **Empty state** ("No leads yet…") when a client has zero leads.
- **Auto-logout** if the token has expired (server returns 401).
- **Live status update** — changing a dropdown updates the screen instantly,
  no page reload.
- **Excel download** works straight from the browser (fetched as a "blob").

### How the Excel download works in the browser
The browser can't just "open" a file from an API call, so we fetch the file as
raw bytes (`responseType: 'blob'`), build a temporary download link in memory,
click it automatically, then throw it away. The file saves as `leads.xlsx`.

### Verified ✅
- `npm run build` compiles with no errors.
- Both servers respond 200 (backend 8000, frontend 5173).

### Status of Step 8
- [x] Dashboard, LeadsTable, StatusDropdown built
- [x] Compiles cleanly
- [ ] Junior dev exercises it in the browser (next)

### The core product loop is now COMPLETE end-to-end 🎉
form submits (Postman) → lead saved → client logs in → sees leads → changes
status → exports Excel. Remaining: Step 9 (email notify), Step 10 (deploy).

---

## Change Request — Client IDs as UUIDs (senior's instruction)

### What the senior asked
> Every client id should be a UUID, and in responses send only the UUID, not
> the primary key (pk).

### Why (the reasoning)
Exposing a database auto-increment id (1, 2, 3…) leaks information — people can
guess how many clients exist and try other ids ("enumeration"). The fix is the
standard pattern: keep the fast integer pk **internal**, and give each client a
random **UUID** that is the only id ever shown to the outside world.

### What we changed
| Area | Before | After |
|------|--------|-------|
| `clients` table | int `id` only | int `id` (internal pk) **+ new `uuid` column** (unique) |
| Create-client response | `{ id: 1, ... }` | `{ uuid: "…", ... }` — **no pk** |
| Login token (`sub`) | the pk (`"1"`) | the client's **uuid** |
| `POST /leads/submit` `client_id` | integer | the client's **uuid** (string) |
| Internal FK `leads.client_id` | int → unchanged | int → unchanged (still references `clients.id`) |

### How it stays consistent
- The token carries the uuid; `get_current_client()` looks the client up by
  uuid and returns the internal id for queries — so all the leads endpoints
  keep working unchanged, and the pk never travels over the wire.
- Lead responses (`LeadOut`) never included `client_id`, so no pk leaked there.

### Files touched
`database/schema.sql`, `database/create_test_client.py`, `backend/models.py`,
`backend/schemas.py`, `backend/auth.py`, `backend/routes/auth.py`,
`backend/routes/leads.py`, `postman/...collection.json`.

### Database migration run on the live DB
```sql
ALTER TABLE clients ADD COLUMN uuid CHAR(36) NULL AFTER id;
UPDATE clients SET uuid = (UUID()) WHERE uuid IS NULL;
ALTER TABLE clients MODIFY COLUMN uuid CHAR(36) NOT NULL DEFAULT (UUID());
ALTER TABLE clients ADD UNIQUE INDEX uq_clients_uuid (uuid);
```

### Verified ✅
| Test | Result |
|------|--------|
| Login token `sub` | is a UUID, not `1` |
| `GET /leads/` after change | still returns the right leads |
| Create-client response | shows `uuid`, no integer pk |
| Submit lead with uuid | `201 Lead received` |
| Submit with fake uuid | `404` |

### Scope note (for the senior)
This applies to the **client** id, exactly as instructed. The lead's own `id`
is still an integer (it isn't a client id, and the dashboard needs it to update
a lead's status). The **frontend needed no changes** — it never sends or shows a
client id; it works off the login token.

### Reminder for testing
The test client's UUID is shown by running
`backend/venv/bin/python database/create_test_client.py`. Use that UUID as
`client_id` when submitting leads in Postman.

---

## Step 9 — Email Notification on New Lead

### What we built
When a new lead is submitted, the client automatically gets an email:
"You have a new lead!" — so they don't have to keep checking the dashboard.

### Provider
**Microsoft 365 / Outlook** SMTP: `smtp.office365.com`, port `587`, STARTTLS.

### Files added/changed
| File | Change |
|------|--------|
| `backend/notifications.py` | New module: composes + sends the email (with dry-run + safe error handling). |
| `backend/routes/leads.py` | Submit route now schedules the email as a background task after saving. |
| `backend/.env` | Added SMTP_HOST/PORT/USER/PASSWORD/FROM (user+password left blank for the dev to fill). |

### Three deliberate design choices
1. **Dry-run mode** — if `SMTP_USER`/`SMTP_PASSWORD` are blank in `.env`, the
   app PRINTS the email to the console instead of sending. Lets us build/test
   without real credentials. Fill them in to go live; no code change needed.
2. **Background sending** — uses FastAPI `BackgroundTasks`, so the form gets its
   instant "Lead received" reply and the email goes out afterwards.
3. **Failure-proof** — `notify_new_lead()` catches and logs any email error, so
   a mail problem can never break the (already-saved) lead. (Senior's rule.)

### Verified ✅
| Test | Result |
|------|--------|
| Submit a lead (dry-run) | lead saved `201` AND email printed to console |
| Email recipient | the owning client's address (from `clients.email`) |
| Email content | correct lead name + message |

### To switch from dry-run to REAL sending (for the dev)
1. Open `backend/.env`.
2. Set `SMTP_USER` = your Outlook/365 email, `SMTP_PASSWORD` = its password
   (or an app password if 2-Step Verification is on), `SMTP_FROM` = same email.
3. Restart the backend. Submit a lead → a real email is sent.
4. **Microsoft caveat:** many Microsoft 365 *business* tenants disable "SMTP
   AUTH" by default. If login fails, an admin must enable SMTP AUTH for the
   mailbox (or use a personal outlook.com account with an app password).

### Status of Step 9
- [x] Email notification built (Outlook/365, background, failure-proof)
- [x] Verified in dry-run mode
- [ ] Dev fills real credentials in `.env` and confirms a live email

### Email status update (Microsoft SMTP saga — PARKED)
Tried sending live via `radlabs.tech` Microsoft 365. Hit walls in order:
1. `535 SmtpClientAuthentication is disabled for the Tenant` → fixed by admin
   unchecking **Settings → Mail flow → Turn off SMTP AUTH protocol** (org-wide).
2. `535 user is locked by your organization's security defaults policy` → blocked
   by **Security Defaults** (org-wide MFA enforcement). Can't exempt one mailbox
   without Conditional Access (needs Entra ID P1; tenant is on Business Basic).
**Conclusion:** password-SMTP via Microsoft is a dead end here. Options to finish
that later: (a) Resend/SendGrid, (b) OAuth2 app registration, (c) disable Security
Defaults (not recommended). Microsoft is **deferred** to later.

### Email now WORKING for testing (GoDaddy mailbox) ✅
For now we test with a GoDaddy-hosted mailbox (`vaibhav@bassiclothing.in`), not
Microsoft. Key finding: even though its webmail is **Titan-branded**
(`secureserver.titan.email`), its SMTP server is GoDaddy's
**`smtpout.secureserver.net`** — NOT `smtp.titan.email`. Using the Titan host
gave a misleading `535 authentication failed` (right password, wrong server).
We found the correct host by reading a working sibling project (`AI_Marketing/.env`).

**Working config (in `backend/.env`, no code change — our STARTTLS path handles it):**
```
SMTP_HOST=smtpout.secureserver.net
SMTP_PORT=587            # 587 STARTTLS or 465 SSL both work
SMTP_USER=vaibhav@bassiclothing.in
SMTP_PASSWORD=Bassi_@16
SMTP_FROM=vaibhav@bassiclothing.in
```
Verified: submitting a lead for that client logged `[EMAIL SENT] ... delivered`.
When switching to the real Microsoft Outlook account later, swap these 5 lines
(and resolve the Microsoft Security-Defaults issue above).

---

## Feature Add — Lead Analytics (triaged from a Google Analytics wishlist)

### What was asked
A 52-item Google Analytics feature list, with instruction to **keep what's
relevant** to this lead dashboard, **discard what isn't**, grouped by complexity.

### The triage (the segregation)
GA mostly measures anonymous web traffic (pageviews, sessions, ad revenue,
demographics) — none of which exist in a private leads inbox. We kept only the
GA *intent* that maps to leads:

| Bucket | Items |
|--------|-------|
| ✅ **BUILD NOW** (trivial, from existing data) | total leads, today, last-7-days, status breakdown, conversion rate (closed÷total), `new→contacted→closed` funnel, 14-day trend |
| 🟡 **MAYBE LATER** (medium) | lead `source`/acquisition (needs a column + form field), date-range filter UI, annotations, Gemini "ask your data" |
| ❌ **DISCARD** (irrelevant to a leads inbox) | pageviews/engagement/bounce, ecommerce, retention/cohorts, demographics/Signals/User-ID, device/geo/landing, audiences/predictive ML, attribution, BigQuery/Looker/Ads/Search Console, consent/IP-anon/bot-filter/DebugView, cross-channel budgeting, campaign import, AI-channel |

### What we built (the green set)
One aggregate endpoint + one read-only UI block. **No new tables, no new
dependencies, no web-tracking pixel.**

| File | Change |
|------|--------|
| `backend/routes/leads.py` | Added `GET /leads/stats` (protected) — totals, by-status, conversion rate, today, last-7-days, 14-day trend. Computed in Python from one query (`# ponytail:` ceiling note: move to SQL GROUP BY only at ~100k+ leads). |
| `frontend/src/components/StatsOverview.jsx` | New: stat cards + pipeline funnel + 14-day trend, **CSS bars only (no chart library)**. Self-hides if stats can't load. |
| `frontend/src/pages/Dashboard.jsx` | Renders `<StatsOverview />` above the leads table. |
| `frontend/src/index.css` | Classes for `.stat-cards`, `.funnel`, `.trend` bars. |

### How it works
`StatsOverview` calls `GET /leads/stats` (token auto-attached). The endpoint
filters by the token's `client_id` (same security as every other route — a
client only sees their own numbers), so no cross-client leakage. The funnel and
trend are proportional-width/height `<div>`s — zero JS charting.

### The logic of each metric (parameter)
All are computed in `GET /leads/stats` from one query of *this client's* leads
(`status` + `submitted_at`). "Today" uses the server's current date.

| Parameter | Plain meaning | How it's calculated |
|-----------|---------------|---------------------|
| `total` | How many leads this client has, ever | Count of all the client's lead rows |
| `by_status.new` | Leads not yet worked | Count of rows where `status = 'new'` |
| `by_status.contacted` | Leads being worked | Count of rows where `status = 'contacted'` |
| `by_status.closed` | Leads finished | Count of rows where `status = 'closed'` |
| `conversion_rate` | % of leads that reached "closed" | `round(closed ÷ total × 100, 1)`; `0.0` if `total = 0` (avoids divide-by-zero) |
| `today` | Leads that came in today | Count where `submitted_at`'s date equals today |
| `last_7_days` | Leads in the past week | Count where `submitted_at` date is **after** (today − 7 days) |
| `trend` | Daily counts for the last 14 days (for the bar chart) | 14 entries, oldest→newest; each is `{date, count}`; days with no leads are **zero-filled** so every bar exists |

**Important assumption — `conversion_rate`:** it treats **`closed` = a win**. The
status model is only `new → contacted → closed` (no "lost" state), so a lead
marked closed-but-lost still counts as a conversion. For a true win-rate, add a
`won` status (or a `closed_reason`) and divide by that instead. (This is the
MAYBE-LATER refinement.)

**How the visuals use these:**
- **Funnel bars** — each status bar's width = `count ÷ max(new,contacted,closed)`,
  so the biggest stage fills the track.
- **Trend bars** — each day's height = `count ÷ max(day counts)`, so the busiest
  day is full-height; empty days show a thin baseline.

### Verified ✅
| Test | Result |
|------|--------|
| `GET /leads/stats` for test@client.com | `total 7, new 5, contacted 2, closed 0` |
| Cross-check vs raw SQL `GROUP BY status` | matches exactly |
| 14-day trend | 7 leads on 06-17, zeros elsewhere (correct) |
| `npm run build` | compiles clean |

### Status
- [x] `/leads/stats` endpoint built + SQL-verified
- [x] `StatsOverview` UI (cards, funnel, trend) built + compiles
- [x] Wired into the dashboard; both servers running
- [ ] Dev eyeballs it in the browser (http://127.0.0.1:5173 → login)

### Deliberately NOT built (scope discipline)
Everything in MAYBE-LATER and DISCARD above. No new npm/pip dependency, no DB
schema change. Lead **source** is the one MAYBE worth doing next if the client
wants "where leads come from" — it needs a `source` column + the public form to
send it.

### Only Step 10 (deploy) remains from the original plan.
