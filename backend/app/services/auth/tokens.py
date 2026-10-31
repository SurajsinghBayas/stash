"""JWT access tokens, opaque refresh/email tokens, and short-lived signed state blobs."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import settings

ALGORITHM = "HS256"


def now() -> datetime:
    return datetime.now(UTC)


def create_access_token(user_id: uuid.UUID) -> str:
    issued = now()
    claims = {
        "sub": str(user_id),
        "iat": issued,
        "exp": issued + timedelta(minutes=settings.access_token_ttl_min),
        "jti": uuid.uuid4().hex,
        "typ": "access",
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None
    if claims.get("typ") != "access":
        return None
    try:
        return uuid.UUID(claims["sub"])
    except ValueError:
        return None


def new_opaque_token() -> tuple[str, str]:
    """Returns (token for the client, sha256 hash for the database)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def sign_state(payload: dict, minutes: int, purpose: str) -> str:
    claims = {**payload, "exp": now() + timedelta(minutes=minutes), "typ": purpose}
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def read_state(token: str, purpose: str) -> dict | None:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    return claims if claims.get("typ") == purpose else None
