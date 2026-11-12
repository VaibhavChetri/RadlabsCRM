"""
config.py
---------
Every setting comes from environment variables (backend/.env locally).
Moving to a server later = set the same variables there. No code change.
"""

import os

from dotenv import load_dotenv

# Real environment variables win over the .env file (tests rely on this).
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is missing. Check backend/.env")
    return value


DATABASE_URL = _required("DATABASE_URL")
SECRET_KEY = _required("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))

# Comma-separated list of frontend origins allowed by CORS.
FRONTEND_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]
