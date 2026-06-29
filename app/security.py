"""Authentication & authorization primitives.

Two principals:
  * photographer (admin) -> static bearer token from config
  * client -> per-gallery passcode exchanged for a short-lived signed token,
    scoped to exactly one gallery. Client-facing reads derive the gallery from
    the token, so cross-gallery access is structurally impossible for them.
"""
import hmac
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Header, HTTPException, status

from app.config import get_settings

settings = get_settings()
_ALGO = "HS256"


# ---- passcodes (hashed at rest) ----
def hash_passcode(passcode: str) -> str:
    return bcrypt.hashpw(passcode.encode(), bcrypt.gensalt()).decode()


def verify_passcode(passcode: str, passcode_hash: str) -> bool:
    try:
        return bcrypt.checkpw(passcode.encode(), passcode_hash.encode())
    except ValueError:
        return False


# ---- client gallery tokens ----
def issue_gallery_token(gallery_id: uuid.UUID) -> tuple[str, int]:
    ttl = settings.client_token_ttl_minutes
    exp = datetime.now(timezone.utc) + timedelta(minutes=ttl)
    token = jwt.encode({"gid": str(gallery_id), "exp": exp}, settings.secret_key, algorithm=_ALGO)
    return token, ttl * 60


def _decode_gallery_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGO])
        return uuid.UUID(payload["gid"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    return authorization.split(" ", 1)[1].strip()


# ---- FastAPI dependencies ----
def require_admin(authorization: str | None = Header(default=None)) -> None:
    token = _bearer(authorization)
    if not hmac.compare_digest(token, settings.admin_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin auth failed")


def require_gallery_access(authorization: str | None = Header(default=None)) -> uuid.UUID:
    """Returns the gallery_id the caller is authorized for. The ONLY gallery they can touch."""
    return _decode_gallery_token(_bearer(authorization))
