"""Google and X sign-in: authorization code + PKCE, state kept in a signed short-lived cookie."""

import asyncio
import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt

from app.config import settings
from app.errors import AppError, NotFound

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
X_AUTH = "https://x.com/i/oauth2/authorize"
X_TOKEN = "https://api.x.com/2/oauth2/token"
X_ME = "https://api.x.com/2/users/me"

_google_jwks = jwt.PyJWKClient(GOOGLE_JWKS, cache_keys=True)


@dataclass
class Profile:
    provider_user_id: str
    email: str | None
    email_verified: bool
    display_name: str | None
    avatar_url: str | None


def redirect_uri(provider: str) -> str:
    return f"{settings.app_url}/api/v1/auth/oauth/{provider}/callback"


def configured(provider: str) -> bool:
    if provider == "google":
        return bool(settings.google_client_id and settings.google_client_secret)
    if provider == "x":
        return bool(settings.x_client_id and settings.x_client_secret)
    return False


def start(provider: str) -> tuple[str, dict]:
    """Returns (provider URL to redirect to, state to keep in the signed cookie)."""
    if not configured(provider):
        raise NotFound(f"{provider} sign-in is not set up", code="provider_not_configured")
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    common = {"response_type": "code", "redirect_uri": redirect_uri(provider), "state": state,
              "code_challenge": challenge, "code_challenge_method": "S256"}
    if provider == "google":
        url = GOOGLE_AUTH + "?" + urlencode({**common, "client_id": settings.google_client_id,
                                             "scope": "openid email profile", "prompt": "select_account"})
    else:
        url = X_AUTH + "?" + urlencode({**common, "client_id": settings.x_client_id,
                                        "scope": "users.read tweet.read offline.access"})
    return url, {"provider": provider, "state": state, "verifier": verifier}


async def finish(provider: str, code: str, verifier: str) -> Profile:
    async with httpx.AsyncClient(timeout=10) as client:
        if provider == "google":
            return await _google(client, code, verifier)
        return await _x(client, code, verifier)


async def _google(client: httpx.AsyncClient, code: str, verifier: str) -> Profile:
    resp = await client.post(GOOGLE_TOKEN, data={
        "code": code, "client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
        "redirect_uri": redirect_uri("google"), "grant_type": "authorization_code", "code_verifier": verifier,
    })
    if resp.status_code != 200:
        raise AppError("Google sign-in failed. Try again.", code="oauth_failed")
    id_token = resp.json().get("id_token", "")
    try:
        key = await asyncio.to_thread(_google_jwks.get_signing_key_from_jwt, id_token)
        claims = jwt.decode(id_token, key.key, algorithms=["RS256"], audience=settings.google_client_id,
                            issuer=["https://accounts.google.com", "accounts.google.com"])
    except jwt.PyJWTError as exc:
        raise AppError("Google sign-in failed. Try again.", code="oauth_failed") from exc
    return Profile(provider_user_id=claims["sub"], email=claims.get("email"),
                   email_verified=bool(claims.get("email_verified")), display_name=claims.get("name"),
                   avatar_url=claims.get("picture"))


async def _x(client: httpx.AsyncClient, code: str, verifier: str) -> Profile:
    resp = await client.post(
        X_TOKEN,
        data={"code": code, "grant_type": "authorization_code", "redirect_uri": redirect_uri("x"),
              "code_verifier": verifier, "client_id": settings.x_client_id},
        auth=(settings.x_client_id or "", settings.x_client_secret or ""),
    )
    if resp.status_code != 200:
        raise AppError("X sign-in failed. Try again.", code="oauth_failed")
    access = resp.json().get("access_token")
    me = await client.get(X_ME, params={"user.fields": "profile_image_url,name,username"},
                          headers={"Authorization": f"Bearer {access}"})
    if me.status_code != 200:
        raise AppError("X sign-in failed. Try again.", code="oauth_failed")
    data = me.json().get("data", {})
    # X does not give a verified email by default; the account is keyed on the X user id.
    return Profile(provider_user_id=str(data["id"]), email=None, email_verified=False,
                   display_name=data.get("name") or data.get("username"), avatar_url=data.get("profile_image_url"))
