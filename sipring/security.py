"""HTTP basic auth helpers.

Auth is enabled by setting SIPRING_USERNAME and SIPRING_PASSWORD. When
enabled it protects the web UI and the /api routes. The /ring endpoints
stay open by design so that simple trigger devices (doorbell buttons,
automations) can call them without credentials.
"""

import base64
import secrets
from typing import Optional

from fastapi import HTTPException, Request, status

from .config import get_settings


def _parse_basic_auth(request: Request) -> Optional[tuple[str, str]]:
    """Return (username, password) from a Basic Authorization header, or None."""
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    try:
        scheme, credentials = auth.split()
        if scheme.lower() != "basic":
            return None
        decoded = base64.b64decode(credentials).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return None


def require_auth(request: Request) -> bool:
    """FastAPI dependency: enforce basic auth when it is configured."""
    settings = get_settings()
    if not settings.auth_enabled:
        return True
    parsed = _parse_basic_auth(request)
    if parsed is not None:
        username, password = parsed
        correct_username = secrets.compare_digest(
            username.encode("utf8"), settings.username.encode("utf8")
        )
        correct_password = secrets.compare_digest(
            password.encode("utf8"), settings.password.encode("utf8")
        )
        if correct_username and correct_password:
            return True
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


def get_source_user(request: Request) -> Optional[str]:
    """Best-effort extraction of the basic-auth username for event logging."""
    if not get_settings().auth_enabled:
        return None
    parsed = _parse_basic_auth(request)
    return parsed[0] if parsed else None
