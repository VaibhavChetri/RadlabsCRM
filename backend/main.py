"""
main.py
-------
Entry point for uvicorn. Run from backend/:
    uvicorn main:app --reload
API docs: http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import FRONTEND_ORIGINS
from routes import auth, imports, leads, lookups

app = FastAPI(title="Radlabs CRM", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # so the browser can read the export's file name
)

app.include_router(auth.router)
app.include_router(leads.router)
app.include_router(lookups.router)
app.include_router(imports.router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "Radlabs CRM"}
