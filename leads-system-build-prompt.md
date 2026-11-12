# Build Prompt: Lead Management System (Backend + Dashboard)
**For:** Junior Developer  
**Target Time:** 3–4 hours  
**Stack:** FastAPI · MySQL · React · JWT Auth  
**Hosting:** GCP (Cloud Run + Cloud SQL)

---

## What You Are Building

A simple lead capture and management system. When a client's website contact form is submitted, the lead gets stored in a central database. The client can then log in at `leads.yourcompany.com` with their credentials and see all their leads — filtered to only their data. They can also export leads as an Excel file.

Think of it as a **private leads inbox** for each client.

---

## Database Design (MySQL)

Create two tables.

**Table: `clients`**
```sql
CREATE TABLE clients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Table: `leads`**
```sql
CREATE TABLE leads (
    id INT AUTO_INCREMENT PRIMARY KEY,
    client_id INT NOT NULL,
    name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    message TEXT,
    status ENUM('new', 'contacted', 'closed') DEFAULT 'new',
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id)
);
```

The `client_id` foreign key ensures each lead belongs to exactly one client. When a client logs in, you only ever return leads where `client_id` matches their account.

---

## Backend (FastAPI + Python)

### Folder Structure
```
backend/
├── main.py
├── database.py
├── models.py
├── schemas.py
├── auth.py
├── routes/
│   ├── auth.py
│   ├── leads.py
│   └── clients.py
├── requirements.txt
└── .env
```

### `requirements.txt`
```
fastapi
uvicorn
sqlalchemy
pymysql
python-jose[cryptography]
passlib[bcrypt]
python-multipart
python-dotenv
openpyxl
```

### `.env`
```
DATABASE_URL=mysql+pymysql://user:password@localhost/leadsdb
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

---

### Auth Logic (`auth.py`)

- Use **JWT tokens** (via `python-jose`)
- Passwords stored as **bcrypt hashes** (via `passlib`)
- On login, verify password → issue a JWT token containing `client_id`
- All protected routes require a valid `Authorization: Bearer <token>` header
- Extract `client_id` from the token in every leads route — **never trust the client to send their own ID**

```python
# How to extract current client from token
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_client(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        client_id = payload.get("sub")
        if client_id is None:
            raise HTTPException(status_code=401)
        return int(client_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

---

### API Endpoints to Build

#### Auth
| Method | Endpoint | What it does |
|--------|----------|--------------|
| POST | `/auth/login` | Takes `email` + `password`, returns JWT token |

#### Leads (all protected)
| Method | Endpoint | What it does |
|--------|----------|--------------|
| POST | `/leads/submit` | Public endpoint — called by the website contact form. Takes `client_id`, name, email, phone, message. No auth needed. |
| GET | `/leads/` | Returns all leads for the logged-in client |
| PATCH | `/leads/{lead_id}/status` | Update lead status to `contacted` or `closed` |
| GET | `/leads/export` | Returns an Excel file download of all leads |

#### Clients (admin only — keep simple for now)
| Method | Endpoint | What it does |
|--------|----------|--------------|
| POST | `/clients/create` | Create a new client account (you'll call this manually or via Postman) |

---

### Lead Submission Endpoint (Important Detail)

This endpoint is **public** — it's what the website contact form will POST to. It should accept a `client_id` in the request body so you know which client the lead belongs to.

```
POST /leads/submit
Body: { client_id, name, email, phone, message }
Response: { "message": "Lead received" }
```

Each client's website will hardcode their own `client_id` in the form submission.

---

### Excel Export

Use `openpyxl` to generate the file. The `/leads/export` endpoint should:
1. Fetch all leads for the current client
2. Create an Excel workbook with columns: Name, Email, Phone, Message, Status, Submitted At
3. Return it as a file download with the correct headers

```python
from fastapi.responses import StreamingResponse
import openpyxl
import io

# Inside the export route:
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["Name", "Email", "Phone", "Message", "Status", "Submitted At"])
for lead in leads:
    ws.append([lead.name, lead.email, lead.phone, lead.message, lead.status, str(lead.submitted_at)])

stream = io.BytesIO()
wb.save(stream)
stream.seek(0)

return StreamingResponse(
    stream,
    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    headers={"Content-Disposition": "attachment; filename=leads.xlsx"}
)
```

---

## Frontend (React)

### What to Build

A simple 3-screen dashboard:

1. **Login screen** — Email + password form → calls `/auth/login` → stores JWT in `localStorage`
2. **Leads table screen** — Shows all leads in a table with columns: Name, Email, Phone, Message, Status, Time. Has a dropdown on each row to change status. Has an "Export to Excel" button.
3. **Empty state** — If no leads yet, show a friendly message

### Tech to Use

- `axios` for API calls
- `react-router-dom` for routing (just 2 routes: `/login` and `/dashboard`)
- Store the JWT token in `localStorage` and send it as `Authorization: Bearer <token>` on every API request

### Suggested Component Structure
```
src/
├── App.jsx
├── api.js              ← axios instance with base URL + auth header
├── pages/
│   ├── Login.jsx
│   └── Dashboard.jsx
└── components/
    ├── LeadsTable.jsx
    └── StatusDropdown.jsx
```

### `api.js` (Axios Setup)
```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'https://your-backend-url.com',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default api;
```

### Login Flow
```javascript
const handleLogin = async () => {
  const res = await api.post('/auth/login', { email, password });
  localStorage.setItem('token', res.data.access_token);
  navigate('/dashboard');
};
```

### Protect the Dashboard Route
If there's no token in `localStorage`, redirect to `/login`.

---

## Email Notification (Simple Version)

When a new lead is submitted via `POST /leads/submit`, also send an email to the client.

Use Python's built-in `smtplib` with Gmail SMTP (or any SMTP provider):

```python
import smtplib
from email.mime.text import MIMEText

def send_notification(to_email, lead_name, lead_message):
    msg = MIMEText(f"New lead from {lead_name}:\n\n{lead_message}")
    msg['Subject'] = 'You have a new lead!'
    msg['From'] = 'noreply@yourcompany.com'
    msg['To'] = to_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login('your-gmail@gmail.com', 'your-app-password')
        server.send_message(msg)
```

Call this function inside the submit lead route after saving to DB. Wrap in a `try/except` so a mail failure doesn't break the lead save.

Store the client's notification email in the `clients` table.

---

## GCP Hosting

**Backend:** Deploy as a container on **Cloud Run**
- Write a `Dockerfile` for the FastAPI app
- Use `uvicorn main:app --host 0.0.0.0 --port 8080`
- Set environment variables in Cloud Run (don't hardcode secrets)

**Database:** Use **Cloud SQL** (MySQL)
- Connect via Cloud SQL connector or internal IP if on same VPC

**Frontend:** Deploy React build to **Firebase Hosting** or **Cloud Storage + CDN**
- Run `npm run build` and deploy the `dist/` folder
- Point `leads.yourcompany.com` to this via DNS

---

## Order of Work (Suggested)

1. Set up MySQL, create both tables, insert one test client manually
2. Build FastAPI skeleton — get `/auth/login` working with JWT
3. Build `/leads/submit` — test via Postman
4. Build `/leads/` GET — confirm it only returns current client's leads
5. Build `/leads/export` — test Excel download
6. Build `PATCH /leads/{id}/status`
7. Build React Login page — test end to end
8. Build React Dashboard with leads table
9. Add email notification
10. Deploy

---

## Things to Be Careful About

- **Never return leads from other clients.** Always filter by `client_id` from the JWT, not from the request body.
- **Hash passwords.** Never store plain text. Use `passlib.hash.bcrypt.hash(password)`.
- **CORS.** Add `CORSMiddleware` in FastAPI so the React app can call the backend.
- **The submit endpoint is public** — anyone with a `client_id` can post a lead. That's fine for now; it's just a form submission.

---

## What's Out of Scope (For Now)

- WhatsApp / Telegram notifications
- Advanced lead pipeline / CRM features
- Multi-user accounts per client
- Admin panel UI

These can be added later. Focus on getting the core loop working: **form submits → lead saved → client logs in → sees lead → exports Excel.**
