"""FastAPI dependency for Firebase Auth token verification.

Verifies Firebase ID tokens using Google's public certificates.
No service account key needed — uses google-auth library.
"""

from __future__ import annotations

import logging

import google.auth.transport.requests
import google.oauth2.id_token
from fastapi import HTTPException, Request

from agent.config.settings import settings

logger = logging.getLogger("agentforge.auth")

# Reusable transport for fetching Google's public certs
_g_request = google.auth.transport.requests.Request()


async def get_current_user(request: Request) -> dict:
    """Extract and validate Firebase ID token from Authorization header.

    Returns dict with uid, email, name, etc.
    Raises 401 HTTPException if token is missing or invalid.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header",
        )

    id_token = auth_header.split("Bearer ", 1)[1]

    try:
        decoded = google.oauth2.id_token.verify_firebase_token(
            id_token,
            _g_request,
            audience=settings.firebase_project_id,
        )
        return {
            "uid": decoded["sub"],
            "email": decoded.get("email", ""),
            "name": decoded.get("name", ""),
        }
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token",
        )
