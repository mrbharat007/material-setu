"""Authentication & role-based access control for Material Setu.

Password hashing with bcrypt, stateless sessions with a signed JWT. The audit
log records the authenticated user behind every ingestion and steward decision.
"""

import os
import time

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import user_repository

SECRET = os.environ.get("MATERIAL_SETU_SECRET", "dev-secret-change-me")
ALGORITHM = "HS256"
TOKEN_TTL = int(os.environ.get("MATERIAL_SETU_TOKEN_TTL", str(60 * 60 * 12)))

ROLES = ("steward", "admin")
_RANK = {role: i for i, role in enumerate(ROLES)}

# Used by scripts/seed.py, which calls the endpoint functions directly (no HTTP
# layer, so no bearer token).
SYSTEM_USER = {
    "id": 0,
    "email": "seed@material-setu.local",
    "name": "Seed script",
    "role": "admin",
    "cpse": None,
}

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_token(user: dict) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "iat": now,
        "exp": now + TOKEN_TTL,
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired — sign in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token")


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if creds is None:
        raise HTTPException(status_code=401, detail="Sign in to continue")

    claims = _decode(creds.credentials)
    user = user_repository.get_user_by_id(int(claims["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="Account no longer exists")

    return {k: user[k] for k in ("id", "email", "name", "role", "cpse")}


def require_role(*allowed: str):
    """Dependency factory: the caller must hold one of ``allowed`` roles (or a
    higher-ranked one)."""
    minimum = min(_RANK[r] for r in allowed)

    def guard(user: dict = Depends(get_current_user)) -> dict:
        if _RANK.get(user["role"], -1) < minimum:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Requires {' or '.join(allowed)} role — "
                    f"your role is {user['role']}"
                ),
            )
        return user

    return guard
