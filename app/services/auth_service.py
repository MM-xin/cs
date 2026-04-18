from __future__ import annotations

from app.core.config import load_user_credentials


def verify_user(username: str, password: str) -> bool:
    credentials = load_user_credentials()
    stored_password = credentials.get(username)
    return stored_password == password
