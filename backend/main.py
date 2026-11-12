"""
main.py
-------
The entry point. This is the file uvicorn runs. It:
  1. Creates the FastAPI app.
  2. Turns on CORS so the React dashboard (a different origin) can call us.
  3. Plugs in our route modules (auth, clients, leads).

Run it from the backend/ folder with:
    uvicorn main:app --reload
Then open http://127.0.0.1:8000/docs for interactive API docs.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import auth, clients, leads

app = FastAPI(title="Lead Management System", version="1.0.0")

# ---- CORS ----
# The React app runs on a different origin (e.g. http://localhost:5173).
# Without this, the browser blocks its requests. For local dev we allow the
# common Vite/React ports; tighten this to the real domain before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routes ----
app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(leads.router)


@app.get("/")
def health_check():
    """A simple 'is the server alive?' check."""
    return {"status": "ok", "service": "Lead Management System"}
